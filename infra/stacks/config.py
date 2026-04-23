from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _bool_env(name: str, default: bool) -> bool:
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
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    project_name: str = "hybrid-ai-platform"
    environment_name: str = "dev"
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
        return cls(
            project_name=os.getenv("PROJECT_NAME", "hybrid-ai-platform").strip()
            or "hybrid-ai-platform",
            environment_name=os.getenv("ENVIRONMENT_NAME", "dev").strip() or "dev",
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
                False,
            ),
            log_retention_days=_int_env("LOG_RETENTION_DAYS", 14),
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
                True,
            ),
        )
