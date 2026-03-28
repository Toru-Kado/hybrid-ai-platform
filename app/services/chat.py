from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.clients.bedrock import BedrockResponse, BedrockRuntimeClient
from app.config.settings import GuardrailSettings, Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatResult:
    response_text: str
    target_id: str
    target_kind: str
    target_source: str
    guardrail_mode: str
    guardrail_identifier: str | None
    guardrail_applied: bool
    guardrail_intervened: bool
    stop_reason: str | None
    service_tier: str | None
    input_tokens: int | None
    output_tokens: int | None
    request_id: str | None
    latency_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "response_text": self.response_text,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "target_source": self.target_source,
            "guardrail_mode": self.guardrail_mode,
            "guardrail_identifier": self.guardrail_identifier,
            "guardrail_applied": self.guardrail_applied,
            "guardrail_intervened": self.guardrail_intervened,
            "stop_reason": self.stop_reason,
            "service_tier": self.service_tier,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
        }


class ChatService:
    def __init__(self, *, client: BedrockRuntimeClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def chat(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> ChatResult:
        effective_system_prompt = system_prompt or self._settings.assistant_system_prompt
        started_at = time.perf_counter()
        response = self._client.send_message(
            prompt=prompt,
            system_prompt=effective_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            guardrail_settings=guardrail_settings,
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        result = _build_chat_result(
            response=response,
            target_id=self._client.target_identifier,
            target_kind=self._settings.runtime_target.kind,
            target_source=self._settings.runtime_target.source_env,
            latency_ms=latency_ms,
            guardrail_settings=guardrail_settings,
        )

        logger.info(
            "Bedrock prompt completed",
            extra={
                "target_id": result.target_id,
                "target_kind": result.target_kind,
                "target_source": result.target_source,
                "guardrail_mode": result.guardrail_mode,
                "guardrail_identifier": result.guardrail_identifier,
                "guardrail_applied": result.guardrail_applied,
                "guardrail_intervened": result.guardrail_intervened,
                "service_tier": result.service_tier,
                "request_id": result.request_id,
                "latency_ms": result.latency_ms,
                "stop_reason": result.stop_reason,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "aws_region": self._settings.aws_region,
            },
        )

        return result


def _build_chat_result(
    *,
    response: BedrockResponse,
    target_id: str,
    target_kind: str,
    target_source: str,
    latency_ms: int,
    guardrail_settings: GuardrailSettings | None,
) -> ChatResult:
    return ChatResult(
        response_text=response.text,
        target_id=target_id,
        target_kind=target_kind,
        target_source=target_source,
        guardrail_mode=guardrail_settings.mode if guardrail_settings else "off",
        guardrail_identifier=(
            guardrail_settings.identifier if guardrail_settings else None
        ),
        guardrail_applied=guardrail_settings is not None,
        guardrail_intervened=response.stop_reason == "guardrail_intervened",
        stop_reason=response.stop_reason,
        service_tier=response.service_tier,
        input_tokens=response.usage_input_tokens,
        output_tokens=response.usage_output_tokens,
        request_id=response.request_id,
        latency_ms=latency_ms,
    )
