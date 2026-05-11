from __future__ import annotations

import logging
import threading
from typing import Any, Iterator, Sequence

from app.clients.base import (
    AssistantClientError,
    AssistantResponse,
    AssistantStreamEvent,
    ConversationTurn,
)
from app.config.settings import GuardrailSettings, Settings

logger = logging.getLogger(__name__)

BedrockClientError = AssistantClientError
BedrockResponse = AssistantResponse

_CREDENTIAL_ERROR_CODES = frozenset({
    "ExpiredToken",
    "ExpiredTokenException",
    "UnauthorizedSSOTokenError",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "NoCredentialsError",
    "TokenRetrievalError",
    "SSOTokenLoadError",
})

_CREDENTIAL_ERROR_PATTERNS = (
    "security token included in the request is expired",
    "the sso session associated with this profile",
    "sso token",
    "token has expired",
    "unable to locate credentials",
)


def _is_credential_error(exc: BaseException) -> bool:
    error_code = exc.__class__.__name__
    if error_code in _CREDENTIAL_ERROR_CODES:
        return True

    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code", "")
        if code in _CREDENTIAL_ERROR_CODES:
            return True

    message = str(exc).lower()
    return any(pattern in message for pattern in _CREDENTIAL_ERROR_PATTERNS)


class BedrockRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        boto3, botocore_config, handled_exceptions = _load_bedrock_dependencies()

        self._boto3 = boto3
        self._botocore_config = botocore_config
        self._settings = settings
        self._handled_exceptions = handled_exceptions
        self._client_lock = threading.Lock()

        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile
        self._session_kwargs = session_kwargs

        try:
            self._client = self._create_boto_client()
        except handled_exceptions as exc:
            raise _normalize_bedrock_error(exc) from exc

    def _create_boto_client(self) -> Any:
        session = self._boto3.Session(**self._session_kwargs)
        return session.client(
            "bedrock-runtime",
            region_name=self._settings.aws_region,
            config=self._botocore_config.Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=120,
            ),
        )

    def _recreate_client(self) -> None:
        with self._client_lock:
            logger.info("Recreating boto3 session to refresh AWS credentials")
            self._client = self._create_boto_client()

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
        conversation: Sequence[ConversationTurn] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> BedrockResponse:
        payload = _build_converse_payload(
            target_identifier=self.target_identifier,
            prompt=prompt,
            conversation=conversation,
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
            if _is_credential_error(exc):
                logger.warning(
                    "Credential error detected, recreating client and retrying",
                    exc_info=True,
                )
                self._recreate_client()
                try:
                    response = self._client.converse(**payload)
                except self._handled_exceptions as retry_exc:
                    raise _normalize_bedrock_error(
                        retry_exc,
                        target_identifier=self.target_identifier,
                        target_kind=self.target_kind,
                    ) from retry_exc
            else:
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

    def stream_message(
        self,
        prompt: str,
        *,
        conversation: Sequence[ConversationTurn] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> Iterator[AssistantStreamEvent]:
        payload = _build_converse_payload(
            target_identifier=self.target_identifier,
            prompt=prompt,
            conversation=conversation,
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
            "Sending Bedrock ConverseStream request",
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
            response = self._client.converse_stream(**payload)
        except self._handled_exceptions as exc:
            if _is_credential_error(exc):
                logger.warning(
                    "Credential error detected, recreating client and retrying",
                    exc_info=True,
                )
                self._recreate_client()
                try:
                    response = self._client.converse_stream(**payload)
                except self._handled_exceptions as retry_exc:
                    raise _normalize_bedrock_error(
                        retry_exc,
                        target_identifier=self.target_identifier,
                        target_kind=self.target_kind,
                    ) from retry_exc
            else:
                raise _normalize_bedrock_error(
                    exc,
                    target_identifier=self.target_identifier,
                    target_kind=self.target_kind,
                ) from exc

        request_id = response.get("ResponseMetadata", {}).get("RequestId")
        yield from _iter_converse_stream_events(
            response.get("stream", []),
            request_id=request_id,
            target_identifier=self.target_identifier,
            target_kind=self.target_kind,
        )


def _build_converse_payload(
    *,
    target_identifier: str,
    prompt: str,
    conversation: Sequence[ConversationTurn] | None,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
    guardrail_settings: GuardrailSettings | None,
    request_metadata: dict[str, str] | None,
) -> dict[str, Any]:
    message_turns = list(conversation) if conversation else [ConversationTurn(role="user", content=prompt)]
    payload: dict[str, Any] = {
        "modelId": target_identifier,
        "messages": _build_messages(message_turns, guardrail_settings),
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


def _build_messages(
    turns: Sequence[ConversationTurn],
    guardrail_settings: GuardrailSettings | None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for turn in turns:
        content = turn.content.strip()
        if not content:
            continue
        if turn.role == "assistant":
            messages.append({"role": "assistant", "content": [{"text": content}]})
            continue
        messages.append(
            {
                "role": "user",
                "content": _build_user_content(content, guardrail_settings),
            }
        )
    return messages


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


def _iter_converse_stream_events(
    stream: Sequence[dict[str, Any]],
    *,
    request_id: str | None,
    target_identifier: str,
    target_kind: str,
) -> Iterator[AssistantStreamEvent]:
    text_chunks: list[str] = []
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    service_tier: str | None = None

    for chunk in stream:
        if not isinstance(chunk, dict):
            continue

        delta_event = chunk.get("contentBlockDelta")
        if isinstance(delta_event, dict):
            delta = delta_event.get("delta", {})
            if isinstance(delta, dict):
                text = delta.get("text")
                if isinstance(text, str) and text:
                    text_chunks.append(text)
                    yield AssistantStreamEvent(type="text_delta", text=text)
            continue

        message_stop = chunk.get("messageStop")
        if isinstance(message_stop, dict):
            stop_reason = message_stop.get("stopReason")
            continue

        metadata = chunk.get("metadata")
        if isinstance(metadata, dict):
            usage = metadata.get("usage", {})
            if isinstance(usage, dict):
                input_tokens = usage.get("inputTokens")
                output_tokens = usage.get("outputTokens")
            performance = metadata.get("performanceConfig", {})
            if isinstance(performance, dict):
                service_tier = performance.get("latency")
            continue

        stream_error = _stream_chunk_error(
            chunk,
            target_identifier=target_identifier,
            target_kind=target_kind,
        )
        if stream_error is not None:
            raise stream_error

    yield AssistantStreamEvent(
        type="complete",
        response=BedrockResponse(
            text="".join(text_chunks),
            stop_reason=stop_reason,
            usage_input_tokens=input_tokens,
            usage_output_tokens=output_tokens,
            request_id=request_id,
            service_tier=service_tier,
        ),
    )


def _stream_chunk_error(
    chunk: dict[str, Any],
    *,
    target_identifier: str,
    target_kind: str,
) -> BedrockClientError | None:
    for error_key, error_code in (
        ("internalServerException", "InternalServerException"),
        ("modelStreamErrorException", "ModelStreamErrorException"),
        ("serviceUnavailableException", "ServiceUnavailableException"),
        ("throttlingException", "ThrottlingException"),
        ("validationException", "ValidationException"),
    ):
        details = chunk.get(error_key)
        if not isinstance(details, dict):
            continue
        return BedrockClientError(
            _normalize_service_error_message(
                service_code=error_code,
                service_message=details.get("message"),
                target_identifier=target_identifier,
                target_kind=target_kind,
            )
            or details.get("message")
            or "Amazon Bedrock streaming failed.",
            error_code=error_code,
        )
    return None


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
