from __future__ import annotations

import re

from aws_cdk import Arn, ArnComponents, Aws, CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

from stacks.config import PlatformConfig


def _sanitize_name(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return sanitized or "hybrid-ai-platform"


def _truncate(value: str, limit: int) -> str:
    return value[:limit].rstrip("-")


def _retention_days(value: int) -> logs.RetentionDays:
    retention_map = {
        1: logs.RetentionDays.ONE_DAY,
        3: logs.RetentionDays.THREE_DAYS,
        5: logs.RetentionDays.FIVE_DAYS,
        7: logs.RetentionDays.ONE_WEEK,
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        60: logs.RetentionDays.TWO_MONTHS,
        90: logs.RetentionDays.THREE_MONTHS,
        120: logs.RetentionDays.FOUR_MONTHS,
        150: logs.RetentionDays.FIVE_MONTHS,
        180: logs.RetentionDays.SIX_MONTHS,
        365: logs.RetentionDays.ONE_YEAR,
        400: logs.RetentionDays.THIRTEEN_MONTHS,
        545: logs.RetentionDays.EIGHTEEN_MONTHS,
        731: logs.RetentionDays.TWO_YEARS,
        1827: logs.RetentionDays.FIVE_YEARS,
        3653: logs.RetentionDays.TEN_YEARS,
        0: logs.RetentionDays.INFINITE,
    }
    try:
        return retention_map[value]
    except KeyError as exc:
        raise ValueError(
            "LOG_RETENTION_DAYS must be one of the CloudWatch-supported values."
        ) from exc


def _bedrock_model_arn(stack: Stack, model_id: str) -> str:
    if model_id.startswith("arn:"):
        return model_id

    return Arn.format(
        ArnComponents(
            service="bedrock",
            region=Aws.REGION,
            account="",
            resource="foundation-model",
            resource_name=model_id,
        ),
        stack,
    )


def _assume_role_principal(arns: list[str]) -> iam.IPrincipal:
    if not arns:
        return iam.AccountRootPrincipal()
    if len(arns) == 1:
        return iam.ArnPrincipal(arns[0])
    return iam.CompositePrincipal(*[iam.ArnPrincipal(arn) for arn in arns])


class HybridAiPlatformBaselineStack(Stack):
    """CDK baseline for the hybrid AI platform account resources."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: PlatformConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        project_name = _sanitize_name(config.project_name)
        environment_name = _sanitize_name(config.environment_name)
        stack_prefix = f"{project_name}-{environment_name}"

        Tags.of(self).add("Company", config.company_name)
        Tags.of(self).add("Project", project_name)
        Tags.of(self).add("Environment", environment_name)
        Tags.of(self).add("ManagedBy", "aws-cdk")
        Tags.of(self).add("Repository", "hybrid-ai-platform")
        if config.organization_segment:
            Tags.of(self).add(
                "OrganizationSegment",
                _sanitize_name(config.organization_segment),
            )

        assets_bucket = s3.Bucket(
            self,
            "AiAssetsBucket",
            bucket_name=config.assets_bucket_name_override,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            auto_delete_objects=config.assets_bucket_force_destroy,
            removal_policy=(
                RemovalPolicy.DESTROY
                if config.assets_bucket_force_destroy
                else RemovalPolicy.RETAIN
            ),
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7)
                )
            ],
        )

        log_group = logs.LogGroup(
            self,
            "AssistantLogGroup",
            log_group_name=f"/aws/{project_name}/{environment_name}/assistant",
            retention=_retention_days(config.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )

        invoke_resources = [
            _bedrock_model_arn(self, model_id)
            for model_id in config.bedrock_foundation_model_ids
        ] + config.bedrock_inference_profile_arns
        if not invoke_resources:
            invoke_resources = ["*"]

        runtime_role_name = _truncate(f"{stack_prefix}-bedrock-runtime", 64)
        runtime_role = iam.Role(
            self,
            "AssistantRuntimeRole",
            role_name=runtime_role_name,
            assumed_by=_assume_role_principal(config.runtime_trusted_principal_arns),
            description="Runtime role for Bedrock-powered hybrid AI platform workloads.",
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockInvoke",
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=invoke_resources,
            )
        )
        if config.bedrock_guardrail_arns:
            runtime_role.add_to_policy(
                iam.PolicyStatement(
                    sid="ApplyBedrockGuardrails",
                    actions=["bedrock:ApplyGuardrail"],
                    resources=config.bedrock_guardrail_arns,
                )
            )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="ListAssetsBucket",
                actions=["s3:GetBucketLocation", "s3:ListBucket"],
                resources=[assets_bucket.bucket_arn],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="ManageAssetsBucketObjects",
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:AbortMultipartUpload",
                ],
                resources=[assets_bucket.arn_for_objects("*")],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                sid="WriteAssistantLogs",
                actions=[
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                ],
                resources=[log_group.log_group_arn, f"{log_group.log_group_arn}:*"],
            )
        )

        operator_role: iam.Role | None = None
        if config.operator_user_name:
            operator_role_name = _truncate(
                config.operator_role_name_override or f"{stack_prefix}-operator",
                64,
            )
            operator_user_arn = (
                f"arn:{Aws.PARTITION}:iam::{Aws.ACCOUNT_ID}:user/{config.operator_user_name}"
            )
            operator_role = iam.Role(
                self,
                "DeveloperOperatorRole",
                role_name=operator_role_name,
                assumed_by=iam.ArnPrincipal(operator_user_arn),
                description="Operator role for local development against the hybrid AI baseline.",
            )
            operator_role.add_to_policy(
                iam.PolicyStatement(
                    sid="BedrockInvoke",
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    resources=invoke_resources,
                )
            )
            if config.bedrock_guardrail_arns:
                operator_role.add_to_policy(
                    iam.PolicyStatement(
                        sid="ApplyBedrockGuardrails",
                        actions=["bedrock:ApplyGuardrail"],
                        resources=config.bedrock_guardrail_arns,
                    )
                )
            operator_role.add_to_policy(
                iam.PolicyStatement(
                    sid="ListAssetsBucket",
                    actions=["s3:GetBucketLocation", "s3:ListBucket"],
                    resources=[assets_bucket.bucket_arn],
                )
            )
            operator_role.add_to_policy(
                iam.PolicyStatement(
                    sid="ManageAssetsBucketObjects",
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:AbortMultipartUpload",
                    ],
                    resources=[assets_bucket.arn_for_objects("*")],
                )
            )
            operator_role.add_to_policy(
                iam.PolicyStatement(
                    sid="WriteAssistantLogs",
                    actions=[
                        "logs:CreateLogStream",
                        "logs:DescribeLogStreams",
                        "logs:PutLogEvents",
                    ],
                    resources=[log_group.log_group_arn, f"{log_group.log_group_arn}:*"],
                )
            )
            if config.operator_role_enable_observability_access:
                operator_role.add_to_policy(
                    iam.PolicyStatement(
                        sid="ReadBedrockObservability",
                        actions=[
                            "bedrock:GetInferenceProfile",
                            "bedrock:ListFoundationModels",
                            "bedrock:ListGuardrails",
                            "bedrock:ListInferenceProfiles",
                            "cloudwatch:GetMetricData",
                            "cloudwatch:GetMetricStatistics",
                            "cloudwatch:ListMetrics",
                            "servicequotas:GetAWSDefaultServiceQuota",
                            "servicequotas:GetServiceQuota",
                            "servicequotas:ListAWSDefaultServiceQuotas",
                            "servicequotas:ListServiceQuotas",
                        ],
                        resources=["*"],
                    )
                )

            iam.CfnUserPolicy(
                self,
                "AllowOperatorUserAssumeRole",
                policy_name=_truncate(f"{operator_role_name}-assume", 128),
                user_name=config.operator_user_name,
                policy_document=iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="AllowAssumeOperatorRole",
                            actions=["sts:AssumeRole"],
                            resources=[operator_role.role_arn],
                        )
                    ]
                ),
            )

        CfnOutput(self, "AiAssetsBucketName", value=assets_bucket.bucket_name)
        CfnOutput(self, "AssistantLogGroupName", value=log_group.log_group_name)
        CfnOutput(self, "AssistantRuntimeRoleArn", value=runtime_role.role_arn)
        CfnOutput(self, "AwsRegion", value=Aws.REGION)
        CfnOutput(
            self,
            "OrganizationSegment",
            value=_sanitize_name(config.organization_segment),
        )
        if operator_role is not None:
            CfnOutput(
                self,
                "DeveloperOperatorRoleArn",
                value=operator_role.role_arn,
            )
            CfnOutput(
                self,
                "DeveloperOperatorRoleName",
                value=operator_role.role_name,
            )
