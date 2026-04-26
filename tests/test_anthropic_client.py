import io
import unittest
from urllib import error

from app.clients.base import ConversationTurn
from app.clients.anthropic import (
    _build_messages_payload,
    _normalize_anthropic_http_error,
)


class AnthropicClientTests(unittest.TestCase):
    def test_builds_messages_payload(self):
        payload = _build_messages_payload(
            model="claude-sonnet-4-5",
            prompt="hello",
            conversation=None,
            system_prompt="system text",
            max_tokens=256,
            temperature=0.3,
        )

        self.assertEqual(payload["model"], "claude-sonnet-4-5")
        self.assertEqual(payload["max_tokens"], 256)
        self.assertEqual(payload["temperature"], 0.3)
        self.assertEqual(payload["system"], "system text")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hello"}])

    def test_builds_messages_payload_with_history(self):
        payload = _build_messages_payload(
            model="claude-sonnet-4-5",
            prompt="ignored fallback",
            conversation=[
                ConversationTurn(role="user", content="first question"),
                ConversationTurn(role="assistant", content="first answer"),
                ConversationTurn(role="user", content="follow up"),
            ],
            system_prompt=None,
            max_tokens=256,
            temperature=0.3,
        )

        self.assertEqual(
            payload["messages"],
            [
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
                {"role": "user", "content": "follow up"},
            ],
        )

    def test_drops_blank_turns_from_history_payload(self):
        payload = _build_messages_payload(
            model="claude-sonnet-4-5",
            prompt="ignored fallback",
            conversation=[
                ConversationTurn(role="user", content="first question"),
                ConversationTurn(role="assistant", content="   "),
                ConversationTurn(role="user", content="follow up"),
            ],
            system_prompt=None,
            max_tokens=256,
            temperature=0.3,
        )

        self.assertEqual(
            payload["messages"],
            [
                {"role": "user", "content": "first question"},
                {"role": "user", "content": "follow up"},
            ],
        )

    def test_normalizes_anthropic_http_error(self):
        response_body = io.BytesIO(
            b'{"type":"error","error":{"type":"rate_limit_error","message":"rate limited"}}'
        )
        self.addCleanup(response_body.close)
        http_error = error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=429,
            msg="Too Many Requests",
            hdrs={"request-id": "req_test"},
            fp=response_body,
        )
        self.addCleanup(http_error.close)

        normalized = _normalize_anthropic_http_error(http_error)

        self.assertEqual(normalized.error_code, "rate_limit_error")
        self.assertIn("rate limited", str(normalized))
        self.assertIn("Request ID: req_test", str(normalized))

    def test_normalizes_anthropic_unauthorized_error_with_key_hint(self):
        response_body = io.BytesIO(
            b'{"type":"error","error":{"type":"authentication_error","message":"invalid key"}}'
        )
        self.addCleanup(response_body.close)
        http_error = error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs={"request-id": "req_auth"},
            fp=response_body,
        )
        self.addCleanup(http_error.close)

        normalized = _normalize_anthropic_http_error(http_error)

        self.assertEqual(normalized.error_code, "authentication_error")
        self.assertIn("Check ANTHROPIC_API_KEY", str(normalized))


if __name__ == "__main__":
    unittest.main()
