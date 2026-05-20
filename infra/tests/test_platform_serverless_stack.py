"""CDK assertion tests for the serverless application stack."""
import json

from aws_cdk import App
from aws_cdk.assertions import Match, Template

from stacks.config import EnvironmentType, ServerlessConfig
from stacks.platform_serverless_stack import HybridAiPlatformServerlessStack


def synth_template(config: ServerlessConfig | None = None) -> Template:
    app = App()
    stack = HybridAiPlatformServerlessStack(
        app,
        "TestHybridAiPlatformServerless",
        config=config or ServerlessConfig(),
    )
    return Template.from_stack(stack)


def test_default_stack_creates_dynamodb_table() -> None:
    template = synth_template()

    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
            "StreamSpecification": {
                "StreamViewType": "NEW_AND_OLD_IMAGES",
            },
        },
    )


def test_default_stack_creates_dynamodb_gsi() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "GlobalSecondaryIndexes": Match.array_with(
                [
                    Match.object_like(
                        {
                            "IndexName": "GSI1",
                            "KeySchema": [
                                {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                                {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                            ],
                        }
                    )
                ]
            ),
        },
    )


def test_default_stack_creates_cognito_user_pool() -> None:
    template = synth_template()

    template.resource_count_is("AWS::Cognito::UserPool", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "AutoVerifiedAttributes": ["email"],
            "MfaConfiguration": "OPTIONAL",
        },
    )


def test_default_stack_creates_cognito_client_without_secret() -> None:
    template = synth_template()

    template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "GenerateSecret": False,
            "ExplicitAuthFlows": Match.array_with(
                ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
            ),
        },
    )


def test_default_stack_creates_api_lambda() -> None:
    template = synth_template()

    # Should have at least 2 Lambda functions (api + stream)
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) >= 2

    # Check API handler exists with correct runtime
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "MemorySize": 512,
            "Timeout": 30,
        },
    )


def test_default_stack_creates_stream_lambda_with_correct_sizing() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "MemorySize": 1024,
            "Timeout": 120,
            "ReservedConcurrentExecutions": 5,
        },
    )


def test_default_stack_creates_http_api() -> None:
    template = synth_template()

    template.resource_count_is("AWS::ApiGatewayV2::Api", 1)
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {
            "ProtocolType": "HTTP",
            "CorsConfiguration": Match.object_like(
                {
                    "AllowMethods": Match.any_value(),
                    "AllowOrigins": ["*"],
                }
            ),
        },
    )


def test_default_stack_creates_function_url() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Lambda::Url",
        {
            "AuthType": "NONE",
            "InvokeMode": "BUFFERED",
        },
    )


def test_default_stack_creates_cloudfront_distribution() -> None:
    template = synth_template()

    template.resource_count_is("AWS::CloudFront::Distribution", 1)
    template.has_resource_properties(
        "AWS::CloudFront::Distribution",
        {
            "DistributionConfig": Match.object_like(
                {
                    "DefaultCacheBehavior": Match.object_like(
                        {"ViewerProtocolPolicy": "redirect-to-https"}
                    ),
                    "CustomErrorResponses": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "ErrorCode": 403,
                                    "ResponseCode": 200,
                                    "ResponsePagePath": "/index.html",
                                }
                            ),
                        ]
                    ),
                }
            ),
        },
    )


def test_default_stack_creates_s3_spa_bucket() -> None:
    template = synth_template()

    # Should have S3 bucket for SPA
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_default_stack_creates_monitoring_resources() -> None:
    template = synth_template()

    # SNS topic for alarms
    template.resource_count_is("AWS::SNS::Topic", 1)

    # CloudWatch alarms
    alarms = template.find_resources("AWS::CloudWatch::Alarm")
    assert len(alarms) >= 3  # api errors, stream errors, latency, dynamo throttle

    # Dashboard
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)


def test_default_stack_does_not_create_opensearch() -> None:
    """Dev environment should not deploy OpenSearch by default."""
    template = synth_template()

    # No OpenSearch collection in dev
    opensearch_collections = template.find_resources(
        "AWS::OpenSearchServerless::Collection"
    )
    assert len(opensearch_collections) == 0


def test_opensearch_enabled_creates_collection() -> None:
    """When OpenSearch is enabled, the collection and indexer are created."""
    template = synth_template(
        ServerlessConfig(enable_opensearch=True)
    )

    template.resource_count_is("AWS::OpenSearchServerless::Collection", 1)

    # Should have 3 Lambda functions (api + stream + indexer)
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) >= 3


def test_prod_config_increases_memory_and_concurrency() -> None:
    template = synth_template(
        ServerlessConfig(
            environment_type=EnvironmentType.PROD,
            environment_name="prod",
            lambda_stream_memory_mb=2048,
            lambda_stream_reserved_concurrency=100,
        )
    )

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "MemorySize": 2048,
            "ReservedConcurrentExecutions": 100,
        },
    )


def test_prod_config_requires_mfa() -> None:
    template = synth_template(
        ServerlessConfig(
            environment_type=EnvironmentType.PROD,
            environment_name="prod",
            cognito_mfa="required",
        )
    )

    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {"MfaConfiguration": "ON"},
    )


def test_stack_exposes_required_outputs() -> None:
    template = synth_template()

    template.has_output("CloudFrontDistributionUrl", {})
    template.has_output("HttpApiUrl", {})
    template.has_output("StreamFunctionUrl", {})
    template.has_output("UserPoolId", {})
    template.has_output("UserPoolClientId", {})
    template.has_output("SessionsTableName", {})
    template.has_output("SpaBucketName", {})


def test_stack_tags_all_resources() -> None:
    template = synth_template()

    # Check that the DynamoDB table has proper tags (each matched individually
    # since array_with requires contiguous matches in order)
    for tag in [
        {"Key": "Project", "Value": "hybrid-ai-platform"},
        {"Key": "Environment", "Value": "dev"},
        {"Key": "ManagedBy", "Value": "aws-cdk"},
        {"Key": "StackType", "Value": "serverless"},
    ]:
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"Tags": Match.array_with([tag])},
        )


def test_dynamodb_pitr_enabled_for_staging() -> None:
    template = synth_template(
        ServerlessConfig(
            environment_type=EnvironmentType.STAGING,
            environment_name="staging",
            dynamodb_pitr=True,
        )
    )

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True},
        },
    )


def test_xray_tracing_enabled_by_default() -> None:
    template = synth_template()

    # Lambda functions should have tracing enabled
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "TracingConfig": {"Mode": "Active"},
        },
    )
