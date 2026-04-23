from __future__ import annotations

import logging
from typing import Any

from app.clients.base import AssistantClientError, AssistantResponse
from app.config.settings import GuardrailSettings, Settings

logger = logging.getLogger(__name__)

BedrockClientError = AssistantClientError
BedrockResponse = AssistantResponse


class BedrockRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        boto3, botocore_config, handled_exceptions = _load_bedrock_dependencies()

        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile

        try:
            session = boto3.Session(**session_kwargs)
            self._client = session.client(
                "bedrock-runtime",
                region_name=settings.aws_region,
                config=botocore_config.Config(
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=120,
                ),
            )
        except handled_exceptions as exc:
            raise _normalize_bedrock_error(exc) from exc

        self._settings = settings
        self._handled_exceptions = handled_exceptions

    @property
    def target_identifier(self) -> str:
        return self._settings.runtime_target.identifier

    @property
    def provider_name(self) -> str:
        return "bedrock"

    @property
    def target_kind(self) -> str:
        return self._settings.runtime_target.kind

    @property
    def target_source(self) -> str:
        return self._settings.runtime_target.source_env

    def send_message(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> BedrockResponse:
        payload = _build_converse_payload(
            target_identifier=self.target_identifier,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens or self._settings.model_max_tokens,
            temperature=(
                temperature
                if temperature is not None
                else self._settings.model_temperature
            ),
            guardrail_settings=guardrail_settings,
            request_metadata=_build_request_metadata(self._settings),
        )

        logger.debug(
            "Sending Bedrock Converse request",
            extra={
                "provider": self.provider_name,
                "aws_region": self._settings.aws_region,
                "target_id": self.target_identifier,
                "target_kind": self.target_kind,
                "target_source": self.target_source,
                "guardrail_mode": guardrail_settings.mode if guardrail_settings else "off",
                "guardrail_identifier": (
                    guardrail_settings.identifier if guardrail_settings else None
                ),
                "guardrail_applied": guardrail_settings is not None,
            },
        )

        try:
            response = self._client.converse(**payload)
        except self._handled_exceptions as exc:
            raise _normalize_bedrock_error(
                exc,
                target_identifier=self.target_identifier,
                target_kind=self.target_kind,
            ) from exc

        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text = "\n".join(
            block["text"]
            for block in content_blocks
            if isinstance(block, dict) and "text" in block
        ).strip()
        usage = response.get("usage", {})
        request_id = response.get("ResponseMetadata", {}).get("RequestId")

        return BedrockResponse(
            text=text,
            stop_reason=response.get("stopReason"),
            usage_input_tokens=usage.get("inputTokens"),
            usage_output_tokens=usage.get("outputTokens"),
            request_id=request_id,
            service_tier=response.get("serviceTier", {}).get("type"),
        )


def _build_converse_payload(
    *,
    target_identifier: str,
    prompt: str,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
    guardrail_settings: GuardrailSettings | None,
    request_metadata: dict[str, str] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "modelId": target_identifier,
        "messages": [
            {
                "role": "user",
                "content": _build_user_content(prompt, guardrail_settings),
            }
        ],
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        },
    }

    if guardrail_settings:
        payload["guardrailConfig"] = {
            "guardrailIdentifier": guardrail_settings.identifier,
            "guardrailVersion": guardrail_settings.version,
        }
        if guardrail_settings.trace:
            payload["guardrailConfig"]["trace"] = "enabled"

    if system_prompt:
        payload["system"] = _build_system_content(system_prompt, guardrail_settings)

    if request_metadata:
        payload["requestMetadata"] = request_metadata

    return payload


def _build_request_metadata(settings: Settings) -> dict[str, str]:
    return {
        "app": settings.app_name,
        "environment": settings.app_env,
        "targetKind": settings.runtime_target.kind,
        "targetSource": settings.runtime_target.source_env,
    }


def _build_user_content(
    prompt: str,
    guardrail_settings: GuardrailSettings | None,
) -> list[dict[str, Any]]:
    if not guardrail_settings:
        return [{"text": prompt}]
    return [_guarded_text_block(prompt)]


def _build_system_content(
    system_prompt: str,
    guardrail_settings: GuardrailSettings | None,
) -> list[dict[str, Any]]:
    if not guardrail_settings or guardrail_settings.mode != "all":
        return [{"text": system_prompt}]
    return [_guarded_text_block(system_prompt)]


def _guarded_text_block(text: str) -> dict[str, Any]:
    return {
        "guardContent": {
            "text": {
                "text": text,
            }
        }
    }


def _load_bedrock_dependencies() -> tuple[Any, Any, tuple[type[BaseException], ...]]:
    try:
        import boto3
        from botocore import config as botocore_config
        from botocore.exceptions import (
            BotoCoreError,
            ClientError,
            EndpointConnectionError,
            NoCredentialsError,
            ParamValidationError,
            ProfileNotFound,
        )
    except ModuleNotFoundError as exc:
        raise BedrockClientError(
            "boto3 is not installed. Install project dependencies with 'pip install -e .'.",
            error_code="MissingDependency",
        ) from exc

    handled_exceptions = (
        BotoCoreError,
        ClientError,
        EndpointConnectionError,
        NoCredentialsError,
        ParamValidationError,
        ProfileNotFound,
    )
    return boto3, botocore_config, handled_exceptions


def _normalize_bedrock_error(
    exc: BaseException,
    *,
    target_identifier: str | None = None,
    target_kind: str | None = None,
) -> BedrockClientError:
    error_code = exc.__class__.__name__

    if error_code == "ProfileNotFound":
        return BedrockClientError(
            "AWS profile was not found. Check AWS_PROFILE and your local AWS CLI configuration.",
            error_code=error_code,
        )

    if error_code == "NoCredentialsError":
        return BedrockClientError(
            "AWS credentials are not available. Run 'aws configure' or export valid AWS credentials.",
            error_code=error_code,
        )

    if error_code == "EndpointConnectionError":
        return BedrockClientError(
            "Could not reach the Bedrock endpoint. Verify AWS_REGION and network access.",
            error_code=error_code,
        )

    if error_code == "ParamValidationError":
        return BedrockClientError(
            f"Invalid Bedrock request parameters: {exc}",
            error_code=error_code,
        )

    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error", {})
        service_code = error.get("Code")
        service_message = error.get("Message")
        if service_code or service_message:
            normalized_message = _normalize_service_error_message(
                service_code=service_code,
                service_message=service_message,
                target_identifier=target_identifier,
                target_kind=target_kind,
            )
            return BedrockClientError(
                normalized_message or "Amazon Bedrock rejected the request.",
                error_code=service_code or error_code,
            )

    return BedrockClientError(str(exc), error_code=error_code)


def _normalize_service_error_message(
    *,
    service_code: str | None,
    service_message: str | None,
    target_identifier: str | None,
    target_kind: str | None,
) -> str | None:
    if not service_code and not service_message:
        return None

    message = service_message or "Amazon Bedrock rejected the request."
    lower_message = message.lower()

    if (
        service_code == "ValidationException"
        and "on-demand throughput" in lower_message
        and target_kind == "model"
    ):
        return (
            f"{message} Configure BEDROCK_INFERENCE_PROFILE_ID or "
            f"BEDROCK_INFERENCE_PROFILE_ARN for a matching inference profile "
            f"instead of invoking the model directly."
        )

    if service_code == "ThrottlingException" and "tokens per day" in lower_message:
        return (
            f"{message} The Bedrock daily token quota for the current account or "
            f"runtime target is exhausted. Wait for the quota window to reset, "
            f"lower BEDROCK_MAX_TOKENS, or switch to a different model or "
            f"inference profile."
        )

    if service_code == "ThrottlingException":
        return (
            f"{message} Bedrock can also throttle on requests per minute or tokens "
            f"per minute. Retry with backoff, reduce concurrency, or lower "
            f"MODEL_MAX_TOKENS for this workload."
        )

    if service_code == "AccessDeniedException":
        if target_kind == "inference_profile":
            return (
                f"{message} Ensure the active AWS identity can call "
                f"bedrock:InvokeModel on the selected inference profile "
                f"({target_identifier})."
            )
        if target_kind == "model":
            return (
                f"{message} Ensure the active AWS identity can call "
                f"bedrock:InvokeModel on the selected model resource "
                f"({target_identifier})."
            )

    if service_code == "ResourceNotFoundException" and target_kind == "inference_profile":
        return (
            f"{message} Verify that the inference profile exists in this account and "
            f"region, and that BEDROCK_INFERENCE_PROFILE_ID or "
            f"BEDROCK_INFERENCE_PROFILE_ARN points to the correct target."
        )

    return message
