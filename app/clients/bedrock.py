from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class BedrockClientError(RuntimeError):
    """Raised when a Bedrock invocation fails."""


@dataclass(slots=True)
class BedrockResponse:
    text: str
    stop_reason: str | None
    usage_input_tokens: int | None
    usage_output_tokens: int | None
    raw_response: dict[str, Any]


class BedrockRuntimeClient:
    def __init__(self, settings: Settings) -> None:
        session_kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.aws_profile:
            session_kwargs["profile_name"] = settings.aws_profile

        session = boto3.Session(**session_kwargs)
        self._client = session.client("bedrock-runtime", region_name=settings.aws_region)
        self._settings = settings

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
            extra={"model_id": self.model_identifier},
        )

        try:
            response = self._client.converse(**payload)
        except (ClientError, BotoCoreError) as exc:
            raise BedrockClientError(str(exc)) from exc

        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text = "\n".join(
            block["text"] for block in content_blocks if isinstance(block, dict) and "text" in block
        ).strip()
        usage = response.get("usage", {})

        return BedrockResponse(
            text=text,
            stop_reason=response.get("stopReason"),
            usage_input_tokens=usage.get("inputTokens"),
            usage_output_tokens=usage.get("outputTokens"),
            raw_response=response,
        )
