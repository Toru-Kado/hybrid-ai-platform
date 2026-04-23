import json

from aws_cdk import App
from aws_cdk.assertions import Match, Template

from stacks.config import PlatformConfig
from stacks.platform_baseline_stack import HybridAiPlatformBaselineStack


def synth_template(config: PlatformConfig | None = None) -> Template:
    app = App()
    stack = HybridAiPlatformBaselineStack(
        app,
        "TestHybridAiPlatformBaseline",
        config=config or PlatformConfig(),
    )
    return Template.from_stack(stack)


def test_default_stack_provisions_bucket_log_group_and_runtime_role() -> None:
    template = synth_template()

    template.resource_count_is("AWS::S3::Bucket", 1)
    template.resource_count_is("AWS::Logs::LogGroup", 1)
    template.resource_count_is("AWS::IAM::Role", 1)
    template.resource_count_is("AWS::IAM::UserPolicy", 0)

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": Match.array_with(
                    [
                        {
                            "ServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            }
                        }
                    ]
                )
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {
            "LogGroupName": "/aws/hybrid-ai-platform/dev/assistant",
            "RetentionInDays": 14,
        },
    )


def test_default_stack_tags_resources_for_new_org_segment() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "Tags": Match.array_with(
                [
                    {"Key": "Company", "Value": "Toru Kado"},
                    {"Key": "ManagedBy", "Value": "aws-cdk"},
                    {"Key": "OrganizationSegment", "Value": "toru-kado"},
                    {"Key": "Project", "Value": "hybrid-ai-platform"},
                ]
            )
        },
    )


def test_runtime_role_keeps_bedrock_s3_and_logs_access() -> None:
    template = synth_template(
        PlatformConfig(
            bedrock_foundation_model_ids=["anthropic.claude-sonnet-4-5"],
            bedrock_inference_profile_arns=[
                "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-4-5-v1:0"
            ],
            bedrock_guardrail_arns=[
                "arn:aws:bedrock:us-east-1:123456789012:guardrail/gr-123456"
            ],
        )
    )

    policy_resources = template.find_resources("AWS::IAM::Policy")
    policy_document = json.dumps(next(iter(policy_resources.values())))

    assert "bedrock:InvokeModel" in policy_document
    assert "bedrock:ApplyGuardrail" in policy_document
    assert "s3:PutObject" in policy_document
    assert "logs:PutLogEvents" in policy_document
    assert "foundation-model/anthropic.claude-sonnet-4-5" in policy_document
    assert "inference-profile/us.anthropic.claude-sonnet-4-5-v1:0" in policy_document


def test_operator_role_is_optional_but_wires_assume_role_when_enabled() -> None:
    template = synth_template(
        PlatformConfig(
            operator_user_name="hybrid-ai-dev",
            operator_role_name_override="HybridAIDevOperatorRole",
        )
    )

    template.resource_count_is("AWS::IAM::Role", 2)
    template.resource_count_is("AWS::IAM::UserPolicy", 1)
    template.has_output("DeveloperOperatorRoleArn", {})
    template.has_output("DeveloperOperatorRoleName", {})


def test_stack_exposes_outputs_for_local_env_wiring() -> None:
    template = synth_template()

    template.has_output("AiAssetsBucketName", {})
    template.has_output("AssistantLogGroupName", {})
    template.has_output("AssistantRuntimeRoleArn", {})
    template.has_output("AwsRegion", {})
    template.has_output("OrganizationSegment", {})
