from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.clients.bedrock import BedrockResponse, BedrockRuntimeClient
from app.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatResult:
    response_text: str
    model_id: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    request_id: str | None
    latency_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "response_text": self.response_text,
            "model_id": self.model_id,
            "stop_reason": self.stop_reason,
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
    ) -> ChatResult:
        effective_system_prompt = system_prompt or self._settings.assistant_system_prompt
        started_at = time.perf_counter()
        response = self._client.send_message(
            prompt=prompt,
            system_prompt=effective_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        result = _build_chat_result(
            response=response,
            model_id=self._client.model_identifier,
            latency_ms=latency_ms,
        )

        logger.info(
            "Bedrock prompt completed",
            extra={
                "model_id": result.model_id,
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
    model_id: str,
    latency_ms: int,
) -> ChatResult:
    return ChatResult(
        response_text=response.text,
        model_id=model_id,
        stop_reason=response.stop_reason,
        input_tokens=response.usage_input_tokens,
        output_tokens=response.usage_output_tokens,
        request_id=response.request_id,
        latency_ms=latency_ms,
    )
