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
