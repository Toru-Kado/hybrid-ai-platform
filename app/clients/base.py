from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config.settings import GuardrailSettings


class AssistantClientError(RuntimeError):
    """Raised when a model provider invocation fails."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(slots=True)
class AssistantResponse:
    text: str
    stop_reason: str | None
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    request_id: str | None
    service_tier: str | None


class AssistantClient(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def target_identifier(self) -> str: ...

    @property
    def target_kind(self) -> str: ...

    @property
    def target_source(self) -> str: ...

    def send_message(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        guardrail_settings: GuardrailSettings | None = None,
    ) -> AssistantResponse: ...
