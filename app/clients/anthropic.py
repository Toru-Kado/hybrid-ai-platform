from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request

from app.clients.base import AssistantClientError, AssistantResponse
from app.config.settings import GuardrailSettings, Settings

logger = logging.getLogger(__name__)


class AnthropicRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def target_identifier(self) -> str:
        return self._settings.runtime_target.identifier

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
    ) -> AssistantResponse:
        if guardrail_settings:
            raise AssistantClientError(
                "Bedrock guardrails are only available with AI_PROVIDER=bedrock. "
                "Set AI_PROVIDER=bedrock or run with --guardrails off.",
                error_code="UnsupportedGuardrails",
            )

        payload = _build_messages_payload(
            model=self.target_identifier,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens or self._settings.model_max_tokens,
            temperature=(
                temperature
                if temperature is not None
                else self._settings.model_temperature
            ),
        )

        logger.debug(
            "Sending Anthropic Messages request",
            extra={
                "provider": self.provider_name,
                "target_id": self.target_identifier,
                "target_kind": self.target_kind,
                "target_source": self.target_source,
            },
        )

        try:
            response = _post_messages_request(
                base_url=self._settings.anthropic_base_url,
                api_key=self._settings.anthropic_api_key,
                api_version=self._settings.anthropic_api_version,
                payload=payload,
            )
        except error.HTTPError as exc:
            raise _normalize_anthropic_http_error(exc) from exc
        except error.URLError as exc:
            raise AssistantClientError(
                "Could not reach the Anthropic API. Verify ANTHROPIC_BASE_URL and network access.",
                error_code="NetworkError",
            ) from exc
        except TimeoutError as exc:
            raise AssistantClientError(
                "The Anthropic API request timed out. Retry the request or reduce MODEL_MAX_TOKENS.",
                error_code="TimeoutError",
            ) from exc

        return _build_anthropic_response(response)


def _build_messages_payload(
    *,
    model: str,
    prompt: str,
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": temperature,
    }
    if system_prompt:
        payload["system"] = system_prompt
    return payload


def _post_messages_request(
    *,
    base_url: str,
    api_key: str,
    api_version: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    encoded_payload = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        url=f"{base_url.rstrip('/')}/v1/messages",
        data=encoded_payload,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": api_version,
        },
        method="POST",
    )
    with request.urlopen(http_request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
        return body, response.headers.get("request-id")


def _build_anthropic_response(
    response: tuple[dict[str, Any], str | None],
) -> AssistantResponse:
    body, request_id = response
    text_blocks = [
        block.get("text", "")
        for block in body.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    usage = body.get("usage", {})
    return AssistantResponse(
        text="\n".join(block for block in text_blocks if block).strip(),
        stop_reason=body.get("stop_reason"),
        usage_input_tokens=usage.get("input_tokens"),
        usage_output_tokens=usage.get("output_tokens"),
        request_id=request_id,
        service_tier=None,
    )


def _normalize_anthropic_http_error(exc: error.HTTPError) -> AssistantClientError:
    error_code = f"HTTP{exc.code}"
    error_message = f"Anthropic API request failed with status {exc.code}."
    response_request_id = exc.headers.get("request-id")

    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = None

    if isinstance(body, dict):
        nested_error = body.get("error", {})
        message = nested_error.get("message")
        error_type = nested_error.get("type")
        if message:
            error_message = message
        if error_type:
            error_code = error_type

    if exc.code == 401:
        error_message = (
            f"{error_message} Check ANTHROPIC_API_KEY and make sure the key is active."
        )
    elif exc.code == 429:
        error_message = (
            f"{error_message} The Anthropic account is currently rate-limited."
        )

    if response_request_id:
        error_message = f"{error_message} Request ID: {response_request_id}."

    return AssistantClientError(error_message, error_code=error_code)
