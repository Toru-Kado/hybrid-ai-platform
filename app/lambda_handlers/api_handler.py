"""API Gateway v2 Lambda proxy handler for REST endpoints.

Routes requests to session CRUD, chat, health, and search endpoints.
Extracts user ID from JWT claims in the API Gateway authorizer context.

Exception handling strategy:
    - AuthError -> 401 (missing/invalid auth context)
    - KeyError -> 404 (session not found)
    - ValueError -> 400 (invalid input)
    - Exception -> 500 (unexpected failures, logged for debugging)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from app.clients.base import ConversationTurn
from app.lambda_handlers.auth import AuthError, extract_user_id_from_event
from app.lambda_handlers.constants import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    ROUTE_CHAT,
    ROUTE_HEALTH,
    ROUTE_SEARCH,
    ROUTE_SESSIONS,
    ROUTE_SESSIONS_ID,
)
from app.lambda_handlers.dynamo_session_store import DynamoSessionStore
from app.lambda_handlers.utils import (
    error_response,
    extract_path_param,
    json_response,
    parse_request_body,
    require_string,
)

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy-initialized globals — persist across warm Lambda invocations to avoid
# repeated initialization (DynamoDB resource creation, Bedrock client setup).
_store: DynamoSessionStore | None = None
_chat_service = None


def _get_store() -> DynamoSessionStore:
    global _store
    if _store is None:
        _store = DynamoSessionStore()
    return _store


def _get_chat_service():
    """Lazy-init chat service to avoid import overhead on cold start for non-chat routes."""
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
    """Lambda handler for API Gateway v2 HTTP API proxy events."""
    raw_path = event.get("rawPath", "")
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    logger.info("Request: %s %s", http_method, raw_path)

    try:
        if raw_path == ROUTE_HEALTH:
            return _health_response()

        user_id = extract_user_id_from_event(event)

        if raw_path == ROUTE_SESSIONS and http_method == "GET":
            return _list_sessions(user_id)

        if raw_path == ROUTE_SESSIONS and http_method == "POST":
            return _create_session(user_id, event)

        if raw_path.startswith(ROUTE_SESSIONS_ID) and http_method == "GET":
            session_id = extract_path_param(raw_path, ROUTE_SESSIONS_ID)
            return _get_session(user_id, session_id)

        if raw_path.startswith(ROUTE_SESSIONS_ID) and http_method == "PATCH":
            session_id = extract_path_param(raw_path, ROUTE_SESSIONS_ID)
            return _update_session(user_id, session_id, event)

        if raw_path.startswith(ROUTE_SESSIONS_ID) and http_method == "DELETE":
            session_id = extract_path_param(raw_path, ROUTE_SESSIONS_ID)
            return _delete_session(user_id, session_id)

        if raw_path == ROUTE_CHAT and http_method == "POST":
            return _handle_chat(user_id, event)

        if raw_path == ROUTE_SEARCH and http_method == "GET":
            return _handle_search(user_id, event)

        return error_response(404, "Not found")

    except AuthError as exc:
        return error_response(exc.status_code, str(exc))
    except KeyError as exc:
        return error_response(404, str(exc))
    except ValueError as exc:
        return error_response(400, str(exc))
    except Exception:
        logger.exception("Unexpected error in %s %s", http_method, raw_path)
        return error_response(500, "Internal server error")


def _health_response() -> dict[str, Any]:
    return json_response(200, {
        "status": "ok",
        "provider": "bedrock",
        "deployment": "serverless",
        "model_id": os.environ.get("BEDROCK_MODEL_ID", ""),
    })


def _list_sessions(user_id: str) -> dict[str, Any]:
    store = _get_store()
    sessions = store.list_sessions(user_id)
    return json_response(200, {"sessions": [s.to_dict() for s in sessions]})


def _create_session(user_id: str, event: dict[str, Any]) -> dict[str, Any]:
    body = parse_request_body(event)
    title = body.get("title") if body else None
    store = _get_store()
    session = store.create_session(user_id, title)
    return json_response(201, {"session": session.to_dict(), "messages": []})


def _get_session(user_id: str, session_id: str) -> dict[str, Any]:
    store = _get_store()
    session = store.get_session(user_id, session_id)
    messages = store.get_messages(user_id, session_id)
    return json_response(200, {
        "session": session.to_dict(),
        "messages": [m.to_dict() for m in messages],
    })


def _update_session(user_id: str, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
    body = parse_request_body(event)
    title = require_string(body, "title")
    store = _get_store()
    store.update_session_title(user_id, session_id, title)
    session = store.get_session(user_id, session_id)
    return json_response(200, {"session": session.to_dict()})


def _delete_session(user_id: str, session_id: str) -> dict[str, Any]:
    store = _get_store()
    store.delete_session(user_id, session_id)
    return json_response(204, None)


def _handle_chat(user_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Non-streaming chat endpoint (JSON request/response).

    Flow: parse request -> ensure session exists -> persist user message ->
    build conversation context -> invoke Bedrock -> persist assistant message ->
    return full result with updated session metadata.
    """
    body = parse_request_body(event)
    prompt = require_string(body, "prompt")
    session_id = body.get("session_id")
    system_prompt = body.get("system_prompt")
    max_tokens = body.get("max_tokens")
    temperature = body.get("temperature")

    store = _get_store()
    session = store.ensure_session(user_id, session_id, prompt=prompt)

    store.add_message(
        user_id=user_id,
        session_id=session.session_id,
        role="user",
        content=prompt,
        metadata={"system_prompt": system_prompt},
    )

    # Build full conversation history for context (ChatService handles trimming)
    messages = store.get_messages(user_id, session.session_id)
    conversation = [
        ConversationTurn(role=m.role, content=m.content) for m in messages
    ]

    chat_service = _get_chat_service()
    result = chat_service.chat(
        prompt=prompt,
        conversation=conversation,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Persist assistant response and return updated session state
    assistant_message = store.add_message(
        user_id=user_id,
        session_id=session.session_id,
        role="assistant",
        content=result.response_text,
        metadata=result.to_dict(),
    )

    persisted_session = store.get_session(user_id, session.session_id)
    return json_response(200, {
        **result.to_dict(),
        "session": persisted_session.to_dict(),
        "message": assistant_message.to_dict(),
    })


def _handle_search(user_id: str, event: dict[str, Any]) -> dict[str, Any]:
    query_params = event.get("queryStringParameters") or {}
    query = query_params.get("q", "").strip()
    if not query:
        raise ValueError("q parameter is required.")

    session_id = query_params.get("session_id")
    limit = min(int(query_params.get("limit", str(DEFAULT_SEARCH_LIMIT))), MAX_SEARCH_LIMIT)

    store = _get_store()
    results = store.search_messages(user_id, query, session_id=session_id, limit=limit)
    return json_response(200, {
        "results": [r.to_dict() for r in results],
        "query": query,
    })
