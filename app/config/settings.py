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

        if line.startswith("export "):
            line = line[len("export ") :].strip()

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


def _log_level_env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().upper()
    allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
    if value not in allowed_levels:
        raise SettingsError(
            f"{name} must be one of: {', '.join(sorted(allowed_levels))}"
        )
    return value


def _looks_like_arn(value: str | None) -> bool:
    return bool(value and value.startswith("arn:"))


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{name} must be a boolean (true/false)")


def _choice_env(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise SettingsError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return value


@dataclass(frozen=True, slots=True)
class GuardrailSettings:
    identifier: str
    version: str
    mode: str
    trace: bool


@dataclass(frozen=True, slots=True)
class RuntimeTarget:
    identifier: str
    kind: str
    source_env: str


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_name: str
    ai_provider: str
    log_level: str
    aws_region: str | None
    aws_profile: str | None
    anthropic_api_key: str | None
    anthropic_model: str | None
    anthropic_base_url: str
    anthropic_api_version: str
    bedrock_model_id: str | None
    bedrock_inference_profile_id: str | None
    bedrock_inference_profile_arn: str | None
    bedrock_guardrail_identifier: str | None
    bedrock_guardrail_version: str | None
    bedrock_guardrail_mode: str
    bedrock_guardrail_trace: bool
    model_max_tokens: int
    model_temperature: float
    context_window_max_turns: int
    context_window_max_chars: int
    assistant_system_prompt: str | None
    ai_assets_bucket_name: str | None
    assistant_log_group_name: str | None

    @property
    def runtime_target(self) -> RuntimeTarget:
        if self.ai_provider == "anthropic":
            if self.anthropic_model:
                return RuntimeTarget(
                    identifier=self.anthropic_model,
                    kind="model",
                    source_env="ANTHROPIC_MODEL",
                )
            raise SettingsError("Set ANTHROPIC_MODEL before running the assistant.")
        if self.bedrock_inference_profile_arn:
            return RuntimeTarget(
                identifier=self.bedrock_inference_profile_arn,
                kind="inference_profile",
                source_env="BEDROCK_INFERENCE_PROFILE_ARN",
            )
        if self.bedrock_inference_profile_id:
            return RuntimeTarget(
                identifier=self.bedrock_inference_profile_id,
                kind="inference_profile",
                source_env="BEDROCK_INFERENCE_PROFILE_ID",
            )
        if self.bedrock_model_id:
            return RuntimeTarget(
                identifier=self.bedrock_model_id,
                kind="model",
                source_env="BEDROCK_MODEL_ID",
            )
        raise SettingsError(
            "Set BEDROCK_MODEL_ID, BEDROCK_INFERENCE_PROFILE_ID, or "
            "BEDROCK_INFERENCE_PROFILE_ARN before running the assistant."
        )

    @property
    def runtime_model_identifier(self) -> str:
        return self.runtime_target.identifier

    def resolve_guardrail_settings(
        self,
        mode_override: str | None = None,
    ) -> GuardrailSettings | None:
        mode = (mode_override or self.bedrock_guardrail_mode).strip().lower()
        allowed_modes = {"off", "user", "all"}
        if mode not in allowed_modes:
            raise SettingsError("Guardrail mode must be one of: all, off, user")
        if self.ai_provider != "bedrock":
            if mode != "off":
                raise SettingsError(
                    "Bedrock guardrails require AI_PROVIDER=bedrock."
                )
            return None
        if mode == "off":
            return None
        if not self.bedrock_guardrail_identifier or not self.bedrock_guardrail_version:
            raise SettingsError(
                "Bedrock guardrails are enabled, but BEDROCK_GUARDRAIL_IDENTIFIER and "
                "BEDROCK_GUARDRAIL_VERSION are not both set."
            )
        return GuardrailSettings(
            identifier=self.bedrock_guardrail_identifier,
            version=self.bedrock_guardrail_version,
            mode=mode,
            trace=self.bedrock_guardrail_trace,
        )

    @classmethod
    def from_env(cls, dotenv_path: str | Path = ".env") -> "Settings":
        load_dotenv(dotenv_path)

        ai_provider = _choice_env("AI_PROVIDER", "bedrock", {"anthropic", "bedrock"})

        model_max_tokens = _int_env(
            "MODEL_MAX_TOKENS",
            _int_env("BEDROCK_MAX_TOKENS", 1024),
        )
        if model_max_tokens <= 0:
            raise SettingsError("MODEL_MAX_TOKENS must be greater than zero")

        model_temperature = _float_env(
            "MODEL_TEMPERATURE",
            _float_env("BEDROCK_TEMPERATURE", 0.2),
        )
        if model_temperature < 0 or model_temperature > 1:
            raise SettingsError("MODEL_TEMPERATURE must be between 0 and 1")

        context_window_max_turns = _int_env("CONTEXT_WINDOW_MAX_TURNS", 24)
        if context_window_max_turns <= 0:
            raise SettingsError("CONTEXT_WINDOW_MAX_TURNS must be greater than zero")

        context_window_max_chars = _int_env("CONTEXT_WINDOW_MAX_CHARS", 24_000)
        if context_window_max_chars <= 0:
            raise SettingsError("CONTEXT_WINDOW_MAX_CHARS must be greater than zero")

        anthropic_api_key = _optional_env("ANTHROPIC_API_KEY")
        anthropic_model = _optional_env("ANTHROPIC_MODEL")
        anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        anthropic_api_version = os.getenv("ANTHROPIC_API_VERSION", "2023-06-01")

        bedrock_model_id = _optional_env("BEDROCK_MODEL_ID")
        bedrock_inference_profile_id = _optional_env("BEDROCK_INFERENCE_PROFILE_ID")
        bedrock_inference_profile_arn = _optional_env("BEDROCK_INFERENCE_PROFILE_ARN")
        if bedrock_model_id and _looks_like_arn(bedrock_model_id):
            raise SettingsError(
                "BEDROCK_MODEL_ID must be a model ID, not an ARN. "
                "Use BEDROCK_INFERENCE_PROFILE_ARN for inference profile ARNs."
            )
        if bedrock_inference_profile_id and _looks_like_arn(
            bedrock_inference_profile_id
        ):
            raise SettingsError(
                "BEDROCK_INFERENCE_PROFILE_ID must be an inference profile ID, not an ARN. "
                "Use BEDROCK_INFERENCE_PROFILE_ARN for inference profile ARNs."
            )
        if bedrock_inference_profile_id and bedrock_inference_profile_arn:
            raise SettingsError(
                "Set only one of BEDROCK_INFERENCE_PROFILE_ID or "
                "BEDROCK_INFERENCE_PROFILE_ARN."
            )
        bedrock_guardrail_identifier = _optional_env("BEDROCK_GUARDRAIL_IDENTIFIER")
        bedrock_guardrail_version = _optional_env("BEDROCK_GUARDRAIL_VERSION")
        if bool(bedrock_guardrail_identifier) != bool(bedrock_guardrail_version):
            raise SettingsError(
                "Set both BEDROCK_GUARDRAIL_IDENTIFIER and BEDROCK_GUARDRAIL_VERSION, or neither."
            )
        bedrock_guardrail_mode = _choice_env(
            "BEDROCK_GUARDRAIL_MODE",
            "user" if bedrock_guardrail_identifier else "off",
            {"off", "user", "all"},
        )
        if (
            ai_provider == "bedrock"
            and bedrock_guardrail_mode != "off"
            and not bedrock_guardrail_identifier
        ):
            raise SettingsError(
                "BEDROCK_GUARDRAIL_MODE requires BEDROCK_GUARDRAIL_IDENTIFIER and BEDROCK_GUARDRAIL_VERSION."
            )
        bedrock_guardrail_trace = _bool_env("BEDROCK_GUARDRAIL_TRACE", False)
        aws_region = _optional_env("AWS_REGION")
        aws_profile = _optional_env("AWS_PROFILE")

        if ai_provider == "anthropic":
            if not anthropic_api_key:
                raise SettingsError("Set ANTHROPIC_API_KEY before running the assistant.")
            if not anthropic_model:
                raise SettingsError("Set ANTHROPIC_MODEL before running the assistant.")
        else:
            if (
                not bedrock_model_id
                and not bedrock_inference_profile_id
                and not bedrock_inference_profile_arn
            ):
                raise SettingsError(
                    "Set BEDROCK_MODEL_ID, BEDROCK_INFERENCE_PROFILE_ID, or "
                    "BEDROCK_INFERENCE_PROFILE_ARN before running the assistant."
                )
            if not aws_region:
                raise SettingsError("Missing required environment variable: AWS_REGION")

        return cls(
            app_env=os.getenv("APP_ENV", "dev"),
            app_name=os.getenv("APP_NAME", "hybrid-ai-assistant"),
            ai_provider=ai_provider,
            log_level=_log_level_env("LOG_LEVEL", "INFO"),
            aws_region=aws_region,
            aws_profile=aws_profile,
            anthropic_api_key=anthropic_api_key,
            anthropic_model=anthropic_model,
            anthropic_base_url=anthropic_base_url.rstrip("/"),
            anthropic_api_version=anthropic_api_version,
            bedrock_model_id=bedrock_model_id,
            bedrock_inference_profile_id=bedrock_inference_profile_id,
            bedrock_inference_profile_arn=bedrock_inference_profile_arn,
            bedrock_guardrail_identifier=bedrock_guardrail_identifier,
            bedrock_guardrail_version=bedrock_guardrail_version,
            bedrock_guardrail_mode=bedrock_guardrail_mode,
            bedrock_guardrail_trace=bedrock_guardrail_trace,
            model_max_tokens=model_max_tokens,
            model_temperature=model_temperature,
            context_window_max_turns=context_window_max_turns,
            context_window_max_chars=context_window_max_chars,
            assistant_system_prompt=_optional_env("ASSISTANT_SYSTEM_PROMPT"),
            ai_assets_bucket_name=_optional_env("AI_ASSETS_BUCKET_NAME"),
            assistant_log_group_name=_optional_env("ASSISTANT_LOG_GROUP_NAME"),
        )
