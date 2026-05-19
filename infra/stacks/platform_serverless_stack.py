"""CDK serverless stack for the hybrid AI platform web application.

Deploys Lambda-backed API Gateway, CloudFront SPA hosting, DynamoDB
persistence, Cognito authentication, and optional OpenSearch for
full-text search. Designed to work alongside the baseline stack.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from stacks.config import ServerlessConfig
from stacks.constructs.api_compute import ApiCompute
from stacks.constructs.cloudfront_distribution import CloudFrontDistribution
from stacks.constructs.cognito_auth import CognitoAuth
from stacks.constructs.dynamodb_table import SessionTable
from stacks.constructs.monitoring import Monitoring
from stacks.constructs.opensearch_collection import OpenSearchCollection
from stacks.constructs.streaming_compute import StreamingCompute
from stacks.utils import retention_days_from_int, sanitize_name


class HybridAiPlatformServerlessStack(Stack):
    """Serverless application stack for the hybrid AI platform.

    Provisions:
        - DynamoDB single-table for sessions/messages
        - Cognito User Pool for authentication
        - API Lambda + HTTP API Gateway (REST endpoints)
        - Streaming Lambda + Function URL (SSE chat streaming)
        - CloudFront + S3 (React SPA hosting)
        - Optional OpenSearch Serverless (full-text search)
        - CloudWatch alarms, dashboard, and SNS notifications
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: ServerlessConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_name = sanitize_name(config.project_name)
        environment_name = sanitize_name(config.environment_name)
        stack_prefix = f"{project_name}-{environment_name}"

        # Tags
        Tags.of(self).add("Company", config.company_name)
        Tags.of(self).add("Project", project_name)
        Tags.of(self).add("Environment", environment_name)
        Tags.of(self).add("ManagedBy", "aws-cdk")
        Tags.of(self).add("Repository", "hybrid-ai-platform")
        Tags.of(self).add("StackType", "serverless")
        if config.organization_segment:
            Tags.of(self).add(
                "OrganizationSegment",
                sanitize_name(config.organization_segment),
            )

        log_retention = retention_days_from_int(config.log_retention_days)

        # Lambda layer packages shared Python dependencies (boto3, etc.) once,
        # reducing individual function deployment size and enabling atomic updates
        lambda_layer = lambda_.LayerVersion(
            self,
            "AppDependenciesLayer",
            layer_version_name=f"{stack_prefix}-deps",
            code=lambda_.Code.from_asset(
                str(Path(__file__).resolve().parents[1] / "lambda-layer"),
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Shared Python dependencies for Lambda handlers",
        )

        # DynamoDB
        session_table_construct = SessionTable(
            self,
            "SessionTable",
            config=config,
            stack_prefix=stack_prefix,
        )

        # Cognito
        cognito_auth = CognitoAuth(
            self,
            "CognitoAuth",
            config=config,
            stack_prefix=stack_prefix,
        )

        # API Compute (Lambda + API Gateway)
        api_compute = ApiCompute(
            self,
            "ApiCompute",
            config=config,
            stack_prefix=stack_prefix,
            lambda_layer=lambda_layer,
            sessions_table=session_table_construct.table,
            user_pool=cognito_auth.user_pool,
            user_pool_client=cognito_auth.user_pool_client,
            log_retention=log_retention,
        )

        # Streaming Compute (Lambda + Function URL)
        streaming_compute = StreamingCompute(
            self,
            "StreamingCompute",
            config=config,
            stack_prefix=stack_prefix,
            lambda_layer=lambda_layer,
            sessions_table=session_table_construct.table,
            user_pool=cognito_auth.user_pool,
            user_pool_client=cognito_auth.user_pool_client,
            log_retention=log_retention,
        )

        # CloudFront + S3
        cdn = CloudFrontDistribution(
            self,
            "CloudFront",
            config=config,
            stack_prefix=stack_prefix,
            http_api=api_compute.http_api,
            function_url=streaming_compute.function_url,
        )

        # OpenSearch (conditional) — only deployed in staging/prod where the
        # ~$700/mo cost is justified. Dev uses DynamoDB scan-based fallback.
        if config.enable_opensearch:
            OpenSearchCollection(
                self,
                "OpenSearch",
                config=config,
                stack_prefix=stack_prefix,
                lambda_layer=lambda_layer,
                sessions_table=session_table_construct.table,
                log_retention=log_retention,
            )

        # Monitoring
        Monitoring(
            self,
            "Monitoring",
            config=config,
            stack_prefix=stack_prefix,
            api_function=api_compute.function,
            stream_function=streaming_compute.function,
            sessions_table=session_table_construct.table,
        )

        # Outputs
        CfnOutput(
            self,
            "CloudFrontDistributionUrl",
            value=f"https://{cdn.distribution.distribution_domain_name}",
            description="CloudFront distribution URL for the SPA",
        )
        CfnOutput(
            self,
            "HttpApiUrl",
            value=api_compute.http_api.url or "",
            description="HTTP API Gateway URL",
        )
        CfnOutput(
            self,
            "StreamFunctionUrl",
            value=streaming_compute.function_url.url,
            description="Lambda Function URL for streaming",
        )
        CfnOutput(
            self,
            "UserPoolId",
            value=cognito_auth.user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=cognito_auth.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
        )
        CfnOutput(
            self,
            "UserPoolDomain",
            value=cognito_auth.user_pool_domain.domain_name,
            description="Cognito hosted UI domain",
        )
        CfnOutput(
            self,
            "SessionsTableName",
            value=session_table_construct.table.table_name,
            description="DynamoDB sessions table name",
        )
        CfnOutput(
            self,
            "SpaBucketName",
            value=cdn.spa_bucket.bucket_name,
            description="S3 bucket for SPA assets",
        )
