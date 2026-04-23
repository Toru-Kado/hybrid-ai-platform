from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from app.clients import AssistantClientError, create_runtime_client
from app.config.logging import configure_logging
from app.config.settings import GuardrailSettings, Settings, SettingsError
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

MAX_REQUEST_BYTES = 128 * 1024


@dataclass(slots=True)
class ServerState:
    settings: Settings
    service: ChatService
    default_guardrails: GuardrailSettings | None


class AssistantApiHandler(BaseHTTPRequestHandler):
    server_version = "HybridAssistantApi/0.1"

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        if self.path == "/api/health":
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

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            payload = self._read_json_body()
            prompt = _required_string(payload, "prompt")
            system_prompt = _optional_string(payload, "system_prompt")
            max_tokens = _optional_positive_int(payload, "max_tokens")
            temperature = _optional_temperature(payload, "temperature")
            guardrails = _optional_guardrail_mode(payload, "guardrails")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        try:
            guardrail_settings = (
                self.state.settings.resolve_guardrail_settings(guardrails)
                if guardrails
                else self.state.default_guardrails
            )
            result = self.state.service.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                guardrail_settings=guardrail_settings,
            )
        except SettingsError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
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

        self._send_json(HTTPStatus.OK, result.to_dict())

    @property
    def state(self) -> ServerState:
        return self.server.state  # type: ignore[attr-defined, no-any-return]

    def log_message(self, format: str, *args: object) -> None:
        logger.info("HTTP request", extra={"client": self.client_address[0]})

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if not raw_length:
            raise ValueError("Request body is required.")

        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer.") from exc

        if content_length <= 0:
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


class AssistantApiServer(ThreadingHTTPServer):
    state: ServerState


def create_server(
    *,
    host: str,
    port: int,
    env_file: str,
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
    )
    return server


def run_server(
    *,
    host: str,
    port: int,
    env_file: str,
    guardrails: str | None = None,
) -> None:
    server = create_server(
        host=host,
        port=port,
        env_file=env_file,
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
    parser.add_argument("--guardrails", choices=["off", "user", "all"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_server(
            host=args.host,
            port=args.port,
            env_file=args.env_file,
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


if __name__ == "__main__":
    raise SystemExit(main())
