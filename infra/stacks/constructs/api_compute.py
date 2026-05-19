"""API Lambda + HTTP API Gateway construct.

Provisions a single Lambda function behind an HTTP API Gateway that handles
all REST endpoints (sessions CRUD, chat, health, search). Routes are proxied
via a Lambda integration; auth is enforced by a Cognito JWT authorizer on all
endpoints except /api/health.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_authorizers as apigwv2_authorizers
from aws_cdk import aws_apigatewayv2_integrations as apigwv2_integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from stacks.config import ServerlessConfig


class ApiCompute(Construct):
    """Lambda function + HTTP API Gateway with JWT authorizer.

    Handles all REST endpoints: sessions CRUD, chat, health, search.
    Routes are proxied to a single Lambda via API Gateway HTTP API.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        stack_prefix: str,
        lambda_layer: lambda_.LayerVersion,
        sessions_table: dynamodb.Table,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        log_retention: logs.RetentionDays,
    ) -> None:
        super().__init__(scope, construct_id)

        api_log_group = logs.LogGroup(
            self,
            "ApiLogGroup",
            log_group_name=f"/aws/lambda/{stack_prefix}-api-handler",
            retention=log_retention,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.function = lambda_.Function(
            self,
            "ApiHandler",
            function_name=f"{stack_prefix}-api-handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.lambda_handlers.api_handler.handler",
            code=lambda_.Code.from_asset(
                str(Path(__file__).resolve().parents[3] / "app"),
            ),
            layers=[lambda_layer],
            memory_size=config.lambda_api_memory_mb,
            timeout=Duration.seconds(30),
            environment={
                "SESSIONS_TABLE_NAME": sessions_table.table_name,
                "POWERTOOLS_SERVICE_NAME": f"{stack_prefix}-api",
                "LOG_LEVEL": "INFO",
                "BEDROCK_MODEL_ID": config.bedrock_model_id,
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
            },
            tracing=lambda_.Tracing.ACTIVE if config.enable_xray else lambda_.Tracing.DISABLED,
            log_group=api_log_group,
        )

        # Grant DynamoDB access for session/message operations
        sessions_table.grant_read_write_data(self.function)

        # Grant Bedrock access for AI model invocation (non-streaming chat endpoint)
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],  # Bedrock doesn't support resource-level permissions
            )
        )

        # Provisioned concurrency reduces cold starts for latency-sensitive prod
        if config.lambda_api_provisioned_concurrency > 0:
            alias = self.function.add_alias(
                "live",
                provisioned_concurrent_executions=config.lambda_api_provisioned_concurrency,
            )

        # JWT authorizer validates Cognito tokens on authenticated routes.
        # API Gateway verifies signature, expiration, issuer, and audience
        # before the request reaches the Lambda function.
        issuer = f"https://cognito-idp.{user_pool.stack.region}.amazonaws.com/{user_pool.user_pool_id}"
        authorizer = apigwv2_authorizers.HttpJwtAuthorizer(
            "JwtAuthorizer",
            jwt_issuer=issuer,
            jwt_audience=[user_pool_client.user_pool_client_id],
        )

        self.http_api = apigwv2.HttpApi(
            self,
            "HttpApi",
            api_name=f"{stack_prefix}-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.POST,
                    apigwv2.CorsHttpMethod.PATCH,
                    apigwv2.CorsHttpMethod.DELETE,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Content-Type", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )

        integration = apigwv2_integrations.HttpLambdaIntegration(
            "ApiIntegration", self.function
        )

        # Health endpoint - no auth
        self.http_api.add_routes(
            path="/api/health",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        # All other routes - JWT auth
        authenticated_routes = [
            ("/api/sessions", [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.POST]),
            ("/api/sessions/{id}", [apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PATCH, apigwv2.HttpMethod.DELETE]),
            ("/api/chat", [apigwv2.HttpMethod.POST]),
            ("/api/search", [apigwv2.HttpMethod.GET]),
        ]
        for path, methods in authenticated_routes:
            self.http_api.add_routes(
                path=path,
                methods=methods,
                integration=integration,
                authorizer=authorizer,
            )
