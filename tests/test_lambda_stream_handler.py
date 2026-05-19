"""Tests for the streaming Lambda handler."""
from __future__ import annotations

import base64
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

from app.lambda_handlers.stream_handler import handler


def _make_valid_token(user_id: str = "stream-user-123") -> str:
    """Build a valid-looking JWT for testing."""
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "token_use": "access",
        "exp": int(time.time()) + 3600,
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
        "client_id": "test-client-id",
    }
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig_b64 = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _stream_event(
    body: dict | None = None,
    token: str | None = None,
    method: str = "POST",
) -> dict:
    """Build a minimal Function URL event."""
    event = {
        "requestContext": {"http": {"method": method}},
        "headers": {},
    }
    if token:
        event["headers"]["authorization"] = f"Bearer {token}"
    if body is not None:
        event["body"] = json.dumps(body)
    return event


@patch.dict(os.environ, {
    "USER_POOL_ID": "us-east-1_TestPool",
    "USER_POOL_CLIENT_ID": "test-client-id",
    "AWS_REGION_NAME": "us-east-1",
    "SESSIONS_TABLE_NAME": "test-table",
})
class StreamHandlerTests(unittest.TestCase):
    """Tests for the stream handler."""

    def test_options_returns_cors_preflight(self):
        event = _stream_event(method="OPTIONS")
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 204)
        self.assertIn("Access-Control-Allow-Methods", result["headers"])

    def test_missing_auth_returns_401(self):
        event = _stream_event(body={"prompt": "hello"})
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 401)

    def test_invalid_token_returns_401(self):
        event = _stream_event(
            body={"prompt": "hello"},
            token="invalid.token",
        )
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 401)

    def test_expired_token_returns_401(self):
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "sub": "user",
            "token_use": "access",
            "exp": int(time.time()) - 3600,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool",
            "client_id": "test-client-id",
        }
        h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        s = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
        token = f"{h}.{p}.{s}"

        event = _stream_event(body={"prompt": "hello"}, token=token)
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 401)

    def test_missing_prompt_returns_400(self):
        token = _make_valid_token()
        event = _stream_event(body={}, token=token)
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("prompt", body["error"])

    def test_empty_prompt_returns_400(self):
        token = _make_valid_token()
        event = _stream_event(body={"prompt": "  "}, token=token)
        result = handler(event, None)
        self.assertEqual(result["statusCode"], 400)

    @patch("app.lambda_handlers.stream_handler._get_chat_service")
    @patch("app.lambda_handlers.stream_handler._get_store")
    def test_successful_stream_returns_sse_events(self, mock_get_store, mock_get_chat_service):
        from app.lambda_handlers.dynamo_session_store import SessionMessage, SessionSummary
        from app.services.chat import ChatResult, ChatStreamEvent

        store = MagicMock()
        store.ensure_session.return_value = SessionSummary(
            session_id="s1", title="Test", created_at="t", updated_at="t",
            message_count=0, preview=None,
        )
        store.add_message.return_value = SessionMessage(
            message_id="m1", session_id="s1", role="user",
            content="hello", created_at="t", metadata=None,
        )
        store.get_messages.return_value = [
            SessionMessage(
                message_id="m1", session_id="s1", role="user",
                content="hello", created_at="t", metadata=None,
            )
        ]
        store.get_session.return_value = SessionSummary(
            session_id="s1", title="Test", created_at="t", updated_at="t",
            message_count=2, preview="response",
        )
        mock_get_store.return_value = store

        chat_result = ChatResult(
            response_text="Hello back!",
            provider="bedrock", target_id="model", target_kind="model",
            target_source="env", guardrail_mode="off",
            guardrail_identifier=None, guardrail_applied=False,
            guardrail_intervened=False, stop_reason="end_turn",
            service_tier=None, input_tokens=10, output_tokens=5,
            request_id="req-1", latency_ms=100,
        )

        chat_service = MagicMock()
        chat_service.stream_chat.return_value = iter([
            ChatStreamEvent(type="text_delta", text="Hello "),
            ChatStreamEvent(type="text_delta", text="back!"),
            ChatStreamEvent(type="complete", result=chat_result),
        ])
        mock_get_chat_service.return_value = chat_service

        token = _make_valid_token()
        event = _stream_event(body={"prompt": "hello"}, token=token)
        result = handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["headers"]["Content-Type"], "text/event-stream")

        body = result["body"]
        self.assertIn("event: session\n", body)
        self.assertIn("event: user_message\n", body)
        self.assertIn("event: delta\n", body)
        self.assertIn("event: complete\n", body)
        self.assertIn('"Hello "', body)


if __name__ == "__main__":
    unittest.main()
