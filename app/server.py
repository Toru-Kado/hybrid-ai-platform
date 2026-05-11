"""HTTP API server for the hybrid AI desktop application.

This module implements a threaded HTTP server that exposes a REST + SSE API
consumed by the Electron/React frontend. It provides session management,
chat (both request-response and streaming via Server-Sent Events), message
search, and inline text completion endpoints.

The Electron main process spawns this server as a subprocess; the frontend
communicates over localhost HTTP. CORS headers are added to allow the Vite
dev server origin during development.

Endpoints:
    GET  /api/health          - Health check with provider info
    GET  /api/sessions        - List all sessions
    GET  /api/sessions/{id}   - Get session with messages
    POST /api/sessions        - Create new session
    PATCH /api/sessions/{id}  - Rename session
    DELETE /api/sessions/{id} - Delete session
    POST /api/chat            - Send message (JSON response)
    POST /api/chat/stream     - Send message (SSE stream)
    POST /api/complete        - Inline text completion
    GET  /api/search          - Full-text search across messages
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.clients import AssistantClientError, create_runtime_client
from app.clients.base import ConversationTurn
from app.config.logging import configure_logging
from app.config.settings import GuardrailSettings, Settings, SettingsError
from app.session_store import SessionStore
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

# Reject request bodies larger than 128 KiB to prevent memory abuse.
MAX_REQUEST_BYTES = 128 * 1024


@dataclass(slots=True)
class ServerState:
    """Shared state accessible to all request handlers.

    Holds the application settings, chat service, guardrail configuration,
    and session store. Attached to the server instance so each handler
    thread can access it without globals.
    """

    settings: Settings
    service: ChatService
    default_guardrails: GuardrailSettings | None
    session_store: SessionStore


class AssistantApiHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing the assistant REST/SSE API.

    Dispatches requests to the appropriate session, chat, or search logic.
    Each instance handles a single request on a thread managed by
    ThreadingHTTPServer.
    """

    server_version = "HybridAssistantApi/0.1"

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        """Route GET requests to health, sessions, or search endpoints."""
        path = self._request_path()
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "provider": self.state.settings.ai_provider,
                    "aws_region": self.state.settings.aws_region,
                    "target_id": self.state.settings.runtime_target.identifier,
                    "target_kind": self.state.settings.runtime_target.kind,
                    "target_source": self.state.settings.runtime_target.source_env,
                },
            )
            return

        if path == "/api/sessions":
            sessions = [item.to_dict() for item in self.state.session_store.list_sessions()]
            self._send_json(HTTPStatus.OK, {"sessions": sessions})
            return

        if path.startswith("/api/sessions/"):
            try:
                session_id = self._session_id_from_path(path)
                payload = self.state.session_store.get_session_payload(session_id)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return

            self._send_json(HTTPStatus.OK, payload)
            return

        if path == "/api/search":
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0].strip()
            if not query:
                self._send_json(
                    HTTPStatus.BAD_REQUEST, {"error": "q parameter is required."}
                )
                return
            session_id_raw = params.get("session_id", [None])[0]
            try:
                session_id = int(session_id_raw) if session_id_raw else None
                limit = min(int(params.get("limit", ["50"])[0]), 100)
                offset = max(int(params.get("offset", ["0"])[0]), 0)
            except (ValueError, TypeError) as exc:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Invalid query parameters."},
                )
                return

            results = self.state.session_store.search_messages(
                query, session_id=session_id, limit=limit, offset=offset
            )
            self._send_json(
                HTTPStatus.OK,
                {"results": [r.to_dict() for r in results], "query": query},
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        """Route POST requests to session creation, chat, or completion endpoints."""
        path = self._request_path()
        if path == "/api/sessions":
            try:
                payload = self._read_json_body(allow_empty=True)
                title = _optional_string(payload, "title") if payload else None
                session = self.state.session_store.create_session(title)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            self._send_json(HTTPStatus.CREATED, {"session": session.to_dict(), "messages": []})
            return

        if path == "/api/chat/stream":
            self._handle_chat_stream()
            return

        if path == "/api/complete":
            try:
                payload = self._read_json_body()
                text = _required_string(payload, "text")
                max_tokens = _optional_positive_int(payload, "max_tokens") or 50
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            if len(text.strip()) < 3:
                self._send_json(HTTPStatus.OK, {"completion": ""})
                return

            try:
                completion = self.state.service.complete(
                    text=text,
                    max_tokens=min(max_tokens, 60),
                )
            except AssistantClientError:
                self._send_json(HTTPStatus.OK, {"completion": ""})
                return
            except Exception:
                logger.exception("Completion request failed")
                self._send_json(HTTPStatus.OK, {"completion": ""})
                return

            self._send_json(HTTPStatus.OK, {"completion": completion})
            return

        if path != "/api/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            payload = self._read_json_body()
            prompt = _required_string(payload, "prompt")
            session_id = _optional_session_id(payload, "session_id")
            system_prompt = _optional_string(payload, "system_prompt")
            max_tokens = _optional_positive_int(payload, "max_tokens")
            temperature = _optional_temperature(payload, "temperature")
            guardrails = _optional_guardrail_mode(payload, "guardrails")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            session = self.state.session_store.ensure_session(session_id, prompt=prompt)
            self.state.session_store.add_message(
                session_id=session.session_id,
                role="user",
                content=prompt,
                metadata={
                    "system_prompt": system_prompt,
                    "guardrails": guardrails,
                },
            )
            conversation = [
                ConversationTurn(role=message.role, content=message.content)
                for message in self.state.session_store.get_messages(session.session_id)
            ]
            guardrail_settings = (
                self.state.settings.resolve_guardrail_settings(guardrails)
                if guardrails
                else self.state.default_guardrails
            )
            result = self.state.service.chat(
                prompt=prompt,
                conversation=conversation,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                guardrail_settings=guardrail_settings,
            )
        except SettingsError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        except AssistantClientError as exc:
            logger.warning("Provider invocation failed", exc_info=True)
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error": str(exc),
                    "error_code": exc.error_code,
                    "provider": self.state.settings.ai_provider,
                },
            )
            return
        except Exception:
            logger.exception("Unexpected API failure")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Unexpected application error."},
            )
            return

        assistant_message = self.state.session_store.add_message(
            session_id=session.session_id,
            role="assistant",
            content=result.response_text,
            metadata=result.to_dict(),
        )
        persisted_session = self.state.session_store.get_session(session.session_id)
        self._send_json(
            HTTPStatus.OK,
            {
                **result.to_dict(),
                "session": persisted_session.to_dict(),
                "message": assistant_message.to_dict(),
            },
        )

    def _handle_chat_stream(self) -> None:
        """Process a streaming chat request, emitting SSE events as tokens arrive.

        Sends session/user_message events first, then delta events for each token,
        and finally a complete event with the full response metadata.
        """
        try:
            payload = self._read_json_body()
            prompt = _required_string(payload, "prompt")
            session_id = _optional_session_id(payload, "session_id")
            system_prompt = _optional_string(payload, "system_prompt")
            max_tokens = _optional_positive_int(payload, "max_tokens")
            temperature = _optional_temperature(payload, "temperature")
            guardrails = _optional_guardrail_mode(payload, "guardrails")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            session = self.state.session_store.ensure_session(session_id, prompt=prompt)
            user_message = self.state.session_store.add_message(
                session_id=session.session_id,
                role="user",
                content=prompt,
                metadata={
                    "system_prompt": system_prompt,
                    "guardrails": guardrails,
                },
            )
            conversation = [
                ConversationTurn(role=message.role, content=message.content)
                for message in self.state.session_store.get_messages(session.session_id)
            ]
            guardrail_settings = (
                self.state.settings.resolve_guardrail_settings(guardrails)
                if guardrails
                else self.state.default_guardrails
            )
        except SettingsError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        self._start_event_stream()
        self._send_sse_event(
            "session",
            {"session": self.state.session_store.get_session(session.session_id).to_dict()},
        )
        self._send_sse_event("user_message", {"message": user_message.to_dict()})

        try:
            result = self._stream_chat_result(
                prompt=prompt,
                conversation=conversation,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                guardrail_settings=guardrail_settings,
            )
        except AssistantClientError as exc:
            logger.warning("Provider invocation failed", exc_info=True)
            self._send_sse_event(
                "error",
                {
                    "error": str(exc),
                    "error_code": exc.error_code,
                    "provider": self.state.settings.ai_provider,
                },
            )
            return
        except Exception:
            logger.exception("Unexpected API failure")
            self._send_sse_event(
                "error",
                {"error": "Unexpected application error."},
            )
            return

        assistant_message = self.state.session_store.add_message(
            session_id=session.session_id,
            role="assistant",
            content=result.response_text,
            metadata=result.to_dict(),
        )
        persisted_session = self.state.session_store.get_session(session.session_id)
        self._send_sse_event(
            "complete",
            {
                **result.to_dict(),
                "session": persisted_session.to_dict(),
                "message": assistant_message.to_dict(),
            },
        )

    def do_PATCH(self) -> None:
        """Handle session title updates."""
        path = self._request_path()
        if not path.startswith("/api/sessions/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            session_id = self._session_id_from_path(path)
            payload = self._read_json_body()
            title = _required_string(payload, "title")
            self.state.session_store.update_session_title(session_id, title)
            session = self.state.session_store.get_session(session_id)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, {"session": session.to_dict()})

    def do_DELETE(self) -> None:
        """Handle session deletion."""
        path = self._request_path()
        if not path.startswith("/api/sessions/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            session_id = self._session_id_from_path(path)
            self.state.session_store.delete_session(session_id)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return

        self._send_empty(HTTPStatus.NO_CONTENT)

    @property
    def state(self) -> ServerState:
        return self.server.state  # type: ignore[attr-defined, no-any-return]

    def log_message(self, format: str, *args: object) -> None:
        logger.info("HTTP request", extra={"client": self.client_address[0]})

    def _request_path(self) -> str:
        return urlparse(self.path).path

    def _read_json_body(self, *, allow_empty: bool = False) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if not raw_length:
            if allow_empty:
                return {}
            raise ValueError("Request body is required.")

        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer.") from exc

        if content_length <= 0:
            if allow_empty:
                return {}
            raise ValueError("Request body is required.")
        if content_length > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")

        return payload

    def _session_id_from_path(self, path: str) -> int:
        try:
            return int(path.rsplit("/", 1)[1])
        except (IndexError, ValueError) as exc:
            raise ValueError("Session id must be an integer.") from exc

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self._send_common_headers()
        self.end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _start_event_stream(self) -> None:
        self.close_connection = True
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

    def _send_sse_event(self, event_name: str, payload: dict[str, Any]) -> None:
        body = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _stream_chat_result(
        self,
        *,
        prompt: str,
        conversation: list[ConversationTurn],
        system_prompt: str | None,
        max_tokens: int | None,
        temperature: float | None,
        guardrail_settings: GuardrailSettings | None,
    ):
        """Consume the chat stream, forwarding text deltas as SSE and returning the final result."""
        result = None
        for event in self.state.service.stream_chat(
            prompt=prompt,
            conversation=conversation,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            guardrail_settings=guardrail_settings,
        ):
            if event.type == "text_delta" and event.text is not None:
                self._send_sse_event("delta", {"text": event.text})
                continue
            if event.type == "complete" and event.result is not None:
                result = event.result

        if result is None:
            raise RuntimeError("Provider stream ended without a final response.")
        return result


class AssistantApiServer(ThreadingHTTPServer):
    """Threaded HTTP server that holds shared ServerState for all request handlers."""

    state: ServerState


def create_server(
    *,
    host: str,
    port: int,
    env_file: str,
    db_path: str,
    guardrails: str | None = None,
) -> AssistantApiServer:
    """Construct and configure the API server with all dependencies.

    Loads settings from the env file, creates the AI client and chat service,
    initializes the SQLite session store, and returns a ready-to-serve instance.
    """
    settings = Settings.from_env(env_file)
    configure_logging(
        level=settings.log_level,
        service_name=settings.app_name,
        environment=settings.app_env,
    )
    client = create_runtime_client(settings=settings)
    service = ChatService(client=client, settings=settings)
    server = AssistantApiServer((host, port), AssistantApiHandler)
    server.state = ServerState(
        settings=settings,
        service=service,
        default_guardrails=settings.resolve_guardrail_settings(guardrails),
        session_store=SessionStore(db_path),
    )
    return server


def run_server(
    *,
    host: str,
    port: int,
    env_file: str,
    db_path: str,
    guardrails: str | None = None,
) -> None:
    """Create and start the API server, blocking until shutdown."""
    server = create_server(
        host=host,
        port=port,
        env_file=env_file,
        db_path=db_path,
        guardrails=guardrails,
    )
    bind_host, bind_port = server.server_address
    logger.info("Assistant API listening", extra={"host": bind_host, "port": bind_port})
    try:
        server.serve_forever()
    finally:
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local HTTP API for the hybrid AI desktop app."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--db-path", default=str(Path(".local") / "assistant.db"))
    parser.add_argument("--guardrails", choices=["off", "user", "all"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_server(
            host=args.host,
            port=args.port,
            env_file=args.env_file,
            db_path=args.db_path,
            guardrails=args.guardrails,
        )
    except SettingsError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Extract a required non-empty string from a JSON payload."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required.")
    return value.strip()


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value.strip() or None


def _optional_positive_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer.")
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero.")
    return value


def _optional_temperature(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number.")
    temperature = float(value)
    if temperature < 0 or temperature > 1:
        raise ValueError(f"{key} must be between 0 and 1.")
    return temperature


def _optional_guardrail_mode(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if value not in {"off", "user", "all"}:
        raise ValueError(f"{key} must be one of: all, off, user.")
    return value


def _optional_session_id(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
