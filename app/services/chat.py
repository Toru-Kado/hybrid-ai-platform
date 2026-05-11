from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Literal, Sequence

from app.clients.base import (
    AssistantClient,
    AssistantResponse,
    AssistantStreamEvent,
    ConversationTurn,
)
from app.config.settings import GuardrailSettings, Settings

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_WINDOW_MAX_TURNS = 24
DEFAULT_CONTEXT_WINDOW_MAX_CHARS = 24_000


@dataclass(slots=True)
class ChatResult:
    response_text: str
    provider: str
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
            "provider": self.provider,
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


@dataclass(slots=True)
class ChatStreamEvent:
    type: Literal["text_delta", "complete"]
    text: str | None = None
    result: ChatResult | None = None


class ChatService:
    def __init__(self, *, client: AssistantClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def chat(
        self,
        *,
        prompt: str,
        conversation: Sequence[ConversationTurn] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> ChatResult:
        effective_system_prompt = system_prompt or self._settings.assistant_system_prompt
        trimmed_conversation = _trim_conversation(
            conversation,
            max_turns=self._settings.context_window_max_turns,
            max_chars=self._settings.context_window_max_chars,
        )
        started_at = time.perf_counter()
        response = self._client.send_message(
            prompt=prompt,
            conversation=trimmed_conversation,
            system_prompt=effective_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            guardrail_settings=guardrail_settings,
        )
        result = _build_logged_chat_result(
            response=response,
            client=self._client,
            settings=self._settings,
            started_at=started_at,
            guardrail_settings=guardrail_settings,
        )
        return result

    def complete(
        self,
        *,
        text: str,
        max_tokens: int = 50,
        temperature: float = 0.6,
    ) -> str:
        """Generate a short text completion (no conversation context, no persistence)."""
        system_prompt = (
            "You are a keystroke prediction engine. You receive partial text that a "
            "human is currently typing into a chat input field. Your ONLY job is to "
            "predict the next few words they will type to finish their message.\n\n"
            "CRITICAL RULES:\n"
            "- Output ONLY the predicted continuation text\n"
            "- NEVER answer questions or respond to the content\n"
            "- NEVER add quotes, prefixes, labels, or explanations\n"
            "- If the text is already a complete sentence, output nothing\n\n"
            "Examples:\n"
            'Input: "How do I"\n'
            'Output: configure my AWS credentials?\n\n'
            'Input: "Can you explain"\n'
            'Output: how the streaming API works?\n\n'
            'Input: "Write a function that"\n'
            'Output: takes a list of numbers and returns the sum\n\n'
            'Input: "What is the difference between"\n'
            'Output: a list and a tuple in Python?\n\n'
            'Input: "Hello, I need help with"\n'
            'Output: setting up my development environment'
        )
        response = self._client.send_message(
            prompt=text,
            conversation=None,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            guardrail_settings=None,
        )
        return response.text.strip()

    def stream_chat(
        self,
        *,
        prompt: str,
        conversation: Sequence[ConversationTurn] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> Iterator[ChatStreamEvent]:
        effective_system_prompt = system_prompt or self._settings.assistant_system_prompt
        trimmed_conversation = _trim_conversation(
            conversation,
            max_turns=self._settings.context_window_max_turns,
            max_chars=self._settings.context_window_max_chars,
        )
        started_at = time.perf_counter()
        final_response: AssistantResponse | None = None

        for event in self._client.stream_message(
            prompt=prompt,
            conversation=trimmed_conversation,
            system_prompt=effective_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            guardrail_settings=guardrail_settings,
        ):
            if event.type == "text_delta" and event.text is not None:
                yield ChatStreamEvent(type="text_delta", text=event.text)
                continue
            if event.type == "complete" and event.response is not None:
                final_response = event.response
                break

        if final_response is None:
            raise RuntimeError("Provider stream ended without a final response.")

        result = _build_logged_chat_result(
            response=final_response,
            client=self._client,
            settings=self._settings,
            started_at=started_at,
            guardrail_settings=guardrail_settings,
        )
        yield ChatStreamEvent(type="complete", result=result)


def _trim_conversation(
    conversation: Sequence[ConversationTurn] | None,
    *,
    max_turns: int = DEFAULT_CONTEXT_WINDOW_MAX_TURNS,
    max_chars: int = DEFAULT_CONTEXT_WINDOW_MAX_CHARS,
) -> list[ConversationTurn] | None:
    if not conversation:
        return None

    retained: list[ConversationTurn] = []
    total_chars = 0

    for turn in reversed(conversation):
        content = turn.content.strip()
        if not content:
            continue

        next_chars = total_chars + len(content)
        if retained and (len(retained) >= max_turns or next_chars > max_chars):
            break

        retained.append(ConversationTurn(role=turn.role, content=content))
        total_chars = next_chars

    retained.reverse()

    while len(retained) > 1 and retained[0].role == "assistant":
        retained.pop(0)

    return retained or None


def _build_chat_result(
    *,
    response: AssistantResponse,
    provider: str,
    target_id: str,
    target_kind: str,
    target_source: str,
    latency_ms: int,
    guardrail_settings: GuardrailSettings | None,
) -> ChatResult:
    return ChatResult(
        response_text=response.text,
        provider=provider,
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


def _build_logged_chat_result(
    *,
    response: AssistantResponse,
    client: AssistantClient,
    settings: Settings,
    started_at: float,
    guardrail_settings: GuardrailSettings | None,
) -> ChatResult:
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    result = _build_chat_result(
        response=response,
        provider=client.provider_name,
        target_id=client.target_identifier,
        target_kind=client.target_kind,
        target_source=client.target_source,
        latency_ms=latency_ms,
        guardrail_settings=guardrail_settings,
    )

    logger.info(
        "Model prompt completed",
        extra={
            "provider": result.provider,
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
            "aws_region": settings.aws_region,
        },
    )

    return result
