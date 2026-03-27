from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Raised when required configuration is missing or invalid."""


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SettingsError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        return int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    try:
        return float(raw)
    except ValueError as exc:
        raise SettingsError(f"{name} must be a float") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_name: str
    log_level: str
    aws_region: str
    aws_profile: str | None
    bedrock_model_id: str | None
    bedrock_inference_profile_arn: str | None
    bedrock_max_tokens: int
    bedrock_temperature: float
    assistant_system_prompt: str | None
    ai_assets_bucket: str | None
    cloudwatch_log_group: str | None

    @property
    def runtime_model_identifier(self) -> str:
        if self.bedrock_inference_profile_arn:
            return self.bedrock_inference_profile_arn
        if self.bedrock_model_id:
            return self.bedrock_model_id
        raise SettingsError(
            "Set BEDROCK_MODEL_ID or BEDROCK_INFERENCE_PROFILE_ARN before running the assistant."
        )

    @classmethod
    def from_env(cls, dotenv_path: str | Path = ".env") -> "Settings":
        load_dotenv(dotenv_path)

        return cls(
            app_env=os.getenv("APP_ENV", "dev"),
            app_name=os.getenv("APP_NAME", "hybrid-ai-assistant"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            aws_region=_required_env("AWS_REGION"),
            aws_profile=_optional_env("AWS_PROFILE"),
            bedrock_model_id=_optional_env("BEDROCK_MODEL_ID"),
            bedrock_inference_profile_arn=_optional_env(
                "BEDROCK_INFERENCE_PROFILE_ARN"
            ),
            bedrock_max_tokens=_int_env("BEDROCK_MAX_TOKENS", 1024),
            bedrock_temperature=_float_env("BEDROCK_TEMPERATURE", 0.2),
            assistant_system_prompt=_optional_env("ASSISTANT_SYSTEM_PROMPT"),
            ai_assets_bucket=_optional_env("AI_ASSETS_BUCKET"),
            cloudwatch_log_group=_optional_env("CLOUDWATCH_LOG_GROUP"),
        )
