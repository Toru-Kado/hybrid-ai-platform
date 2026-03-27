from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class BedrockClientError(RuntimeError):
    """Raised when a Bedrock invocation fails."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(slots=True)
class BedrockResponse:
    text: str
    stop_reason: str | None
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    request_id: str | None


class BedrockRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        boto3, botocore_config, handled_exceptions = _load_bedrock_dependencies()

        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile

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
        self._settings = settings
        self._handled_exceptions = handled_exceptions

    @property
    def model_identifier(self) -> str:
        return self._settings.runtime_model_identifier

    def send_message(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> BedrockResponse:
        payload: dict[str, Any] = {
            "modelId": self.model_identifier,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens or self._settings.bedrock_max_tokens,
                "temperature": (
                    temperature
                    if temperature is not None
                    else self._settings.bedrock_temperature
                ),
            },
        }

        if system_prompt:
            payload["system"] = [{"text": system_prompt}]

        logger.debug(
            "Sending Bedrock Converse request",
            extra={
                "aws_region": self._settings.aws_region,
                "model_id": self.model_identifier,
            },
        )

        try:
            response = self._client.converse(**payload)
        except self._handled_exceptions as exc:
            raise _normalize_bedrock_error(exc) from exc

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
        )


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


def _normalize_bedrock_error(exc: BaseException) -> BedrockClientError:
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
            return BedrockClientError(
                service_message or "Amazon Bedrock rejected the request.",
                error_code=service_code or error_code,
            )

    return BedrockClientError(str(exc), error_code=error_code)
