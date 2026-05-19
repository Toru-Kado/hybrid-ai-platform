"""CDK stack configuration dataclasses and environment presets.

Provides PlatformConfig (baseline infrastructure) and ServerlessConfig
(application stack) with environment-aware defaults loaded from env vars.
Each config is a frozen dataclass instantiated via from_env() class method.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class EnvironmentType(Enum):
    """Supported deployment environments."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"

    @classmethod
    def from_string(cls, value: str) -> "EnvironmentType":
        normalized = value.lower().strip()
        try:
            return cls(normalized)
        except ValueError as exc:
            valid = ", ".join(e.value for e in cls)
            raise ValueError(
                f"ENVIRONMENT_TYPE must be one of: {valid}"
            ) from exc


# --- Environment variable parsing helpers ---
# These provide typed access to env vars with validation and defaults.


def _csv_env(name: str) -> list[str]:
    """Parse a comma-separated env var into a list of trimmed strings."""
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
    """Parse a boolean env var (accepts: true/false, yes/no, 1/0, on/off)."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (true/false)")


def _int_env(name: str, default: int) -> int:
    """Parse an integer env var with a fallback default."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _environment_presets(env_type: EnvironmentType) -> dict:
    """Return sensible defaults for an environment type."""
    presets = {
        EnvironmentType.DEV: {
            "assets_bucket_force_destroy": True,
            "log_retention_days": 7,
            "operator_role_enable_observability_access": True,
        },
        EnvironmentType.STAGING: {
            "assets_bucket_force_destroy": False,
            "log_retention_days": 30,
            "operator_role_enable_observability_access": True,
        },
        EnvironmentType.PROD: {
            "assets_bucket_force_destroy": False,
            "log_retention_days": 90,
            "operator_role_enable_observability_access": False,
        },
    }
    return presets.get(env_type, {})


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    project_name: str = "hybrid-ai-platform"
    environment_name: str = "dev"
    environment_type: EnvironmentType = EnvironmentType.DEV
    company_name: str = "Toru Kado"
    organization_segment: str = "toru-kado"
    assets_bucket_name_override: str | None = None
    assets_bucket_force_destroy: bool = False
    log_retention_days: int = 14
    bedrock_foundation_model_ids: list[str] = field(default_factory=list)
    bedrock_inference_profile_arns: list[str] = field(default_factory=list)
    bedrock_guardrail_arns: list[str] = field(default_factory=list)
    runtime_trusted_principal_arns: list[str] = field(default_factory=list)
    operator_user_name: str | None = None
    operator_role_name_override: str | None = None
    operator_role_enable_observability_access: bool = True

    @classmethod
    def from_env(cls) -> "PlatformConfig":
        env_type_str = os.getenv("ENVIRONMENT_TYPE", "dev").strip().lower()
        try:
            env_type = EnvironmentType.from_string(env_type_str)
        except ValueError as exc:
            raise ValueError(f"Invalid ENVIRONMENT_TYPE: {env_type_str}") from exc

        presets = _environment_presets(env_type)
        environment_name = (
            os.getenv("ENVIRONMENT_NAME", "").strip()
            or env_type.value
        )

        return cls(
            project_name=os.getenv("PROJECT_NAME", "hybrid-ai-platform").strip()
            or "hybrid-ai-platform",
            environment_name=environment_name,
            environment_type=env_type,
            company_name=os.getenv("COMPANY_NAME", "Toru Kado").strip()
            or "Toru Kado",
            organization_segment=os.getenv(
                "ORGANIZATION_SEGMENT",
                "toru-kado",
            ).strip()
            or "toru-kado",
            assets_bucket_name_override=(
                os.getenv("ASSETS_BUCKET_NAME_OVERRIDE", "").strip() or None
            ),
            assets_bucket_force_destroy=_bool_env(
                "ASSETS_BUCKET_FORCE_DESTROY",
                presets.get("assets_bucket_force_destroy", False),
            ),
            log_retention_days=_int_env(
                "LOG_RETENTION_DAYS",
                presets.get("log_retention_days", 14),
            ),
            bedrock_foundation_model_ids=_csv_env("BEDROCK_FOUNDATION_MODEL_IDS"),
            bedrock_inference_profile_arns=_csv_env(
                "BEDROCK_INFERENCE_PROFILE_ARNS"
            ),
            bedrock_guardrail_arns=_csv_env("BEDROCK_GUARDRAIL_ARNS"),
            runtime_trusted_principal_arns=_csv_env(
                "RUNTIME_TRUSTED_PRINCIPAL_ARNS"
            ),
            operator_user_name=os.getenv("OPERATOR_USER_NAME", "").strip() or None,
            operator_role_name_override=(
                os.getenv("OPERATOR_ROLE_NAME_OVERRIDE", "").strip() or None
            ),
            operator_role_enable_observability_access=_bool_env(
                "OPERATOR_ROLE_ENABLE_OBSERVABILITY_ACCESS",
                presets.get("operator_role_enable_observability_access", True),
            ),
        )


def _serverless_presets(env_type: EnvironmentType) -> dict:
    """Return sensible serverless defaults for an environment type."""
    presets = {
        EnvironmentType.DEV: {
            "lambda_api_memory_mb": 512,
            "lambda_stream_memory_mb": 1024,
            "lambda_stream_timeout_seconds": 120,
            "lambda_stream_reserved_concurrency": 0,
            "lambda_api_provisioned_concurrency": 0,
            "cognito_self_signup": True,
            "cognito_mfa": "optional",
            "dynamodb_pitr": False,
            "dynamodb_ttl_days": 30,
            "enable_opensearch": False,
            "enable_xray": True,
            "log_retention_days": 7,
        },
        EnvironmentType.STAGING: {
            "lambda_api_memory_mb": 1024,
            "lambda_stream_memory_mb": 1024,
            "lambda_stream_timeout_seconds": 150,
            "lambda_stream_reserved_concurrency": 20,
            "lambda_api_provisioned_concurrency": 0,
            "cognito_self_signup": True,
            "cognito_mfa": "optional",
            "dynamodb_pitr": True,
            "dynamodb_ttl_days": 90,
            "enable_opensearch": True,
            "enable_xray": True,
            "log_retention_days": 30,
        },
        EnvironmentType.PROD: {
            "lambda_api_memory_mb": 1024,
            "lambda_stream_memory_mb": 2048,
            "lambda_stream_timeout_seconds": 180,
            "lambda_stream_reserved_concurrency": 100,
            "lambda_api_provisioned_concurrency": 2,
            "cognito_self_signup": False,
            "cognito_mfa": "required",
            "dynamodb_pitr": True,
            "dynamodb_ttl_days": 0,
            "enable_opensearch": True,
            "enable_xray": True,
            "log_retention_days": 90,
        },
    }
    return presets.get(env_type, {})


@dataclass(frozen=True, slots=True)
class ServerlessConfig:
    """Configuration for the serverless application stack.

    Controls Lambda sizing, Cognito auth behavior, DynamoDB durability,
    OpenSearch enablement, CloudFront distribution, and monitoring.
    All fields have sensible dev defaults; production overrides come
    from environment presets or explicit env var overrides.
    """

    project_name: str = "hybrid-ai-platform"
    environment_name: str = "dev"
    environment_type: EnvironmentType = EnvironmentType.DEV
    company_name: str = "Toru Kado"
    organization_segment: str = "toru-kado"

    # Lambda sizing — API handler has lower memory needs (CRUD ops);
    # streaming handler needs more for holding Bedrock response in memory.
    lambda_api_memory_mb: int = 512
    lambda_stream_memory_mb: int = 1024
    lambda_stream_timeout_seconds: int = 120
    lambda_stream_reserved_concurrency: int = 5
    # Provisioned concurrency avoids cold starts for high-traffic prod
    lambda_api_provisioned_concurrency: int = 0

    # Auth — Cognito User Pool settings
    cognito_self_signup: bool = True  # Disabled in prod (admin-only registration)
    cognito_mfa: str = "optional"  # off | optional | required

    # Database — DynamoDB durability settings
    dynamodb_pitr: bool = False  # Point-in-time recovery (enabled staging/prod)
    dynamodb_ttl_days: int = 30  # 0 means no TTL (data never auto-expires)

    # Search — OpenSearch Serverless (~$700/mo baseline, dev uses DynamoDB fallback)
    enable_opensearch: bool = False

    # Frontend — CloudFront custom domain (requires ACM cert in us-east-1)
    custom_domain_name: str | None = None
    custom_domain_certificate_arn: str | None = None
    waf_web_acl_arn: str | None = None  # WAF WebACL for rate limiting

    # Monitoring
    alarm_notification_email: str | None = None
    enable_xray: bool = True
    log_retention_days: int = 14

    # Bedrock model used by both Lambda handlers
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-v1:0"

    @classmethod
    def from_env(cls) -> "ServerlessConfig":
        env_type_str = os.getenv("ENVIRONMENT_TYPE", "dev").strip().lower()
        try:
            env_type = EnvironmentType.from_string(env_type_str)
        except ValueError as exc:
            raise ValueError(f"Invalid ENVIRONMENT_TYPE: {env_type_str}") from exc

        presets = _serverless_presets(env_type)
        environment_name = (
            os.getenv("ENVIRONMENT_NAME", "").strip() or env_type.value
        )

        cognito_mfa = os.getenv("COGNITO_MFA", "").strip().lower()
        if cognito_mfa and cognito_mfa not in {"off", "optional", "required"}:
            raise ValueError("COGNITO_MFA must be one of: off, optional, required")

        return cls(
            project_name=os.getenv("PROJECT_NAME", "hybrid-ai-platform").strip()
            or "hybrid-ai-platform",
            environment_name=environment_name,
            environment_type=env_type,
            company_name=os.getenv("COMPANY_NAME", "Toru Kado").strip()
            or "Toru Kado",
            organization_segment=os.getenv(
                "ORGANIZATION_SEGMENT", "toru-kado"
            ).strip()
            or "toru-kado",
            lambda_api_memory_mb=_int_env(
                "LAMBDA_API_MEMORY_MB",
                presets.get("lambda_api_memory_mb", 512),
            ),
            lambda_stream_memory_mb=_int_env(
                "LAMBDA_STREAM_MEMORY_MB",
                presets.get("lambda_stream_memory_mb", 1024),
            ),
            lambda_stream_timeout_seconds=_int_env(
                "LAMBDA_STREAM_TIMEOUT_SECONDS",
                presets.get("lambda_stream_timeout_seconds", 120),
            ),
            lambda_stream_reserved_concurrency=_int_env(
                "LAMBDA_STREAM_RESERVED_CONCURRENCY",
                presets.get("lambda_stream_reserved_concurrency", 5),
            ),
            lambda_api_provisioned_concurrency=_int_env(
                "LAMBDA_API_PROVISIONED_CONCURRENCY",
                presets.get("lambda_api_provisioned_concurrency", 0),
            ),
            cognito_self_signup=_bool_env(
                "COGNITO_SELF_SIGNUP",
                presets.get("cognito_self_signup", True),
            ),
            cognito_mfa=cognito_mfa or presets.get("cognito_mfa", "optional"),
            dynamodb_pitr=_bool_env(
                "DYNAMODB_PITR",
                presets.get("dynamodb_pitr", False),
            ),
            dynamodb_ttl_days=_int_env(
                "DYNAMODB_TTL_DAYS",
                presets.get("dynamodb_ttl_days", 30),
            ),
            enable_opensearch=_bool_env(
                "ENABLE_OPENSEARCH",
                presets.get("enable_opensearch", False),
            ),
            custom_domain_name=(
                os.getenv("CUSTOM_DOMAIN_NAME", "").strip() or None
            ),
            custom_domain_certificate_arn=(
                os.getenv("CUSTOM_DOMAIN_CERTIFICATE_ARN", "").strip() or None
            ),
            waf_web_acl_arn=(
                os.getenv("WAF_WEB_ACL_ARN", "").strip() or None
            ),
            alarm_notification_email=(
                os.getenv("ALARM_NOTIFICATION_EMAIL", "").strip() or None
            ),
            enable_xray=_bool_env(
                "ENABLE_XRAY",
                presets.get("enable_xray", True),
            ),
            log_retention_days=_int_env(
                "LOG_RETENTION_DAYS",
                presets.get("log_retention_days", 14),
            ),
            bedrock_model_id=os.getenv(
                "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-v1:0"
            ).strip(),
        )
