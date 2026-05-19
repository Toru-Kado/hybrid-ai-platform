"""Lambda response streaming handler for SSE chat.

Uses Lambda Function URL with RESPONSE_STREAM invoke mode to deliver
Server-Sent Events to the client. Auth is validated in handler code
since Function URLs don't support JWT authorizers natively.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.clients.base import ConversationTurn
from app.lambda_handlers.auth import (
    AuthError,
    extract_token_from_header,
    validate_token,
)
from app.lambda_handlers.dynamo_session_store import DynamoSessionStore
from app.lambda_handlers.utils import (
    cors_preflight_response,
    error_response,
    parse_request_body,
    require_string,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy-initialized globals
_store: DynamoSessionStore | None = None
_chat_service = None


def _get_store() -> DynamoSessionStore:
    global _store
    if _store is None:
        _store = DynamoSessionStore()
    return _store


def _get_chat_service():
    """Lazy-init chat service.

    Deferred imports avoid loading heavy Bedrock/Settings modules
    during cold start if the request fails auth or validation first.
    The service is cached in a module-level global for reuse across
    warm invocations.
    """
    global _chat_service
    if _chat_service is None:
        from app.clients.bedrock import BedrockRuntimeClient
        from app.config.settings import Settings
        from app.services.chat import ChatService

        settings = Settings.from_env(os.environ.get("ENV_FILE", ".env"))
        client = BedrockRuntimeClient(settings)
        _chat_service = ChatService(client=client, settings=settings)
    return _chat_service


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda Function URL streaming handler.

    Returns SSE-formatted response. For true streaming, a Lambda Web
    Adapter or custom runtime integration is required; this implementation
    collects all events and returns them as a single response body.
    """
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return cors_preflight_response()

    headers = event.get("headers", {})

    # Validate JWT
    try:
        token = extract_token_from_header(headers)
        claims = validate_token(token)
        user_id = claims.sub
    except AuthError as exc:
        logger.warning("Auth failed: %s", exc)
        return error_response(exc.status_code, str(exc))

    # Parse request body
    try:
        body = parse_request_body(event)
        prompt = require_string(body, "prompt")
        session_id = body.get("session_id")
        system_prompt = body.get("system_prompt")
        max_tokens = body.get("max_tokens")
        temperature = body.get("temperature")
    except ValueError as exc:
        return error_response(400, str(exc))

    # Session management
    store = _get_store()
    try:
        session = store.ensure_session(user_id, session_id, prompt=prompt)

        user_message = store.add_message(
            user_id=user_id,
            session_id=session.session_id,
            role="user",
            content=prompt,
            metadata={"system_prompt": system_prompt},
        )

        messages = store.get_messages(user_id, session.session_id)
        conversation = [
            ConversationTurn(role=m.role, content=m.content) for m in messages
        ]
    except KeyError as exc:
        return error_response(404, str(exc))
    except Exception:
        logger.exception("Session setup failed")
        return error_response(500, "Failed to initialize session")

    # Stream chat response and collect SSE events.
    # SSE protocol: each event has a type (event:) and JSON payload (data:).
    # Events are sent in order: session -> user_message -> delta(s) -> complete.
    chat_service = _get_chat_service()
    sse_chunks: list[str] = []

    # Emit session and user message metadata before streaming AI response
    sse_chunks.append(_format_sse("session", {"session": session.to_dict()}))
    sse_chunks.append(_format_sse("user_message", {"message": user_message.to_dict()}))

    try:
        final_result = None
        for stream_event in chat_service.stream_chat(
            prompt=prompt,
            conversation=conversation,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            if stream_event.type == "text_delta" and stream_event.text is not None:
                sse_chunks.append(_format_sse("delta", {"text": stream_event.text}))
            elif stream_event.type == "complete" and stream_event.result is not None:
                final_result = stream_event.result

        if final_result is None:
            raise RuntimeError("Provider stream ended without a final response.")

        assistant_message = store.add_message(
            user_id=user_id,
            session_id=session.session_id,
            role="assistant",
            content=final_result.response_text,
            metadata=final_result.to_dict(),
        )

        persisted_session = store.get_session(user_id, session.session_id)
        sse_chunks.append(
            _format_sse(
                "complete",
                {
                    **final_result.to_dict(),
                    "session": persisted_session.to_dict(),
                    "message": assistant_message.to_dict(),
                },
            )
        )

    except Exception as exc:
        logger.exception("Stream processing failed")
        sse_chunks.append(_format_sse("error", {"error": str(exc)}))

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": "".join(sse_chunks),
    }


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Event."""
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
