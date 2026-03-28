"""External service clients."""

from app.clients.anthropic import AnthropicRuntimeClient
from app.clients.base import AssistantClient, AssistantClientError
from app.clients.bedrock import BedrockRuntimeClient
from app.config.settings import Settings


def create_runtime_client(settings: Settings) -> AssistantClient:
    if settings.ai_provider == "anthropic":
        return AnthropicRuntimeClient(settings=settings)
    return BedrockRuntimeClient(settings=settings)


__all__ = [
    "AssistantClient",
    "AssistantClientError",
    "AnthropicRuntimeClient",
    "BedrockRuntimeClient",
    "create_runtime_client",
]
