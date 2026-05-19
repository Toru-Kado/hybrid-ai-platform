"""Streaming Lambda with Function URL construct.

Provisions a Lambda function with a Function URL configured for response
streaming (RESPONSE_STREAM invoke mode). This enables Server-Sent Events
delivery for real-time chat responses. Auth is set to NONE at the URL level
because Function URLs don't support JWT authorizers — validation happens
in the handler code instead.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from stacks.config import ServerlessConfig


class StreamingCompute(Construct):
    """Lambda function with Function URL configured for response streaming.

    Handles SSE chat streaming via Lambda response streaming (RESPONSE_STREAM
    invoke mode). Auth is validated in handler code since Function URLs don't
    support JWT authorizers natively.
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

        stream_log_group = logs.LogGroup(
            self,
            "StreamLogGroup",
            log_group_name=f"/aws/lambda/{stack_prefix}-stream-handler",
            retention=log_retention,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.function = lambda_.Function(
            self,
            "StreamHandler",
            function_name=f"{stack_prefix}-stream-handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.lambda_handlers.stream_handler.handler",
            code=lambda_.Code.from_asset(
                str(Path(__file__).resolve().parents[3] / "app"),
            ),
            layers=[lambda_layer],
            memory_size=config.lambda_stream_memory_mb,
            timeout=Duration.seconds(config.lambda_stream_timeout_seconds),
            # Only set reserved concurrency if explicitly configured above 0.
            # Accounts with low limits (default 10) can't reserve without going
            # below the 10-unreserved minimum required by Lambda.
            reserved_concurrent_executions=(
                config.lambda_stream_reserved_concurrency
                if config.lambda_stream_reserved_concurrency > 0
                else None
            ),
            environment={
                "SESSIONS_TABLE_NAME": sessions_table.table_name,
                "POWERTOOLS_SERVICE_NAME": f"{stack_prefix}-stream",
                "LOG_LEVEL": "INFO",
                "BEDROCK_MODEL_ID": config.bedrock_model_id,
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client.user_pool_client_id,
                "AWS_REGION_NAME": user_pool.stack.region,
            },
            tracing=lambda_.Tracing.ACTIVE if config.enable_xray else lambda_.Tracing.DISABLED,
            log_group=stream_log_group,
        )

        # Grant DynamoDB access for persisting messages during stream
        sessions_table.grant_read_write_data(self.function)

        # Grant Bedrock access for streaming model invocation
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )

        # Function URL with BUFFERED invoke mode. The handler collects all SSE
        # events and returns them as a single response body. Auth type NONE means
        # the URL is publicly accessible; JWT validation is in the handler code.
        self.function_url = self.function.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            invoke_mode=lambda_.InvokeMode.BUFFERED,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[lambda_.HttpMethod.ALL],
                allowed_headers=["Content-Type", "Authorization"],
                max_age=Duration.hours(1),
            ),
        )
