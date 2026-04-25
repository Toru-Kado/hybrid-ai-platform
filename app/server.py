from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.clients import AssistantClientError, create_runtime_client
from app.clients.base import ConversationTurn
from app.config.logging import configure_logging
from app.config.settings import GuardrailSettings, Settings, SettingsError
from app.session_store import SessionStore
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 128 * 1024


@dataclass(slots=True)
class ServerState:
    settings: Settings
    service: ChatService
    default_guardrails: GuardrailSettings | None
    session_store: SessionStore


class AssistantApiHandler(BaseHTTPRequestHandler):
    server_version = "HybridAssistantApi/0.1"

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
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

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
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

    def do_PATCH(self) -> None:
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
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


class AssistantApiServer(ThreadingHTTPServer):
    state: ServerState


def create_server(
    *,
    host: str,
    port: int,
    env_file: str,
    db_path: str,
    guardrails: str | None = None,
) -> AssistantApiServer:
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
