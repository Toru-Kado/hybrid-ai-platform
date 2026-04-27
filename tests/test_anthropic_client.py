import io
import unittest
from urllib import error

from app.clients.base import ConversationTurn
from app.clients.anthropic import (
    _build_messages_payload,
    _iter_anthropic_stream_events,
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

    def test_collects_text_deltas_from_anthropic_stream(self):
        response = FakeStreamingResponse(
            b"event: message_start\n"
            b'data: {"message":{"usage":{"input_tokens":11,"output_tokens":0}}}\n\n'
            b"event: content_block_delta\n"
            b'data: {"delta":{"text":"Streaming "}}\n\n'
            b"event: content_block_delta\n"
            b'data: {"delta":{"text":"works"}}\n\n'
            b"event: message_delta\n"
            b'data: {"delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":7}}\n\n'
            b"event: message_stop\n"
            b"data: {}\n\n",
            request_id="req-stream",
        )

        events = list(_iter_anthropic_stream_events(response))

        self.assertEqual(events[0].type, "text_delta")
        self.assertEqual(events[0].text, "Streaming ")
        self.assertEqual(events[1].text, "works")
        self.assertEqual(events[-1].type, "complete")
        self.assertEqual(events[-1].response.text, "Streaming works")
        self.assertEqual(events[-1].response.stop_reason, "end_turn")
        self.assertEqual(events[-1].response.usage_input_tokens, 11)
        self.assertEqual(events[-1].response.usage_output_tokens, 7)
        self.assertEqual(events[-1].response.request_id, "req-stream")


class FakeStreamingResponse(io.BytesIO):
    def __init__(self, body: bytes, *, request_id: str) -> None:
        super().__init__(body)
        self.headers = {"request-id": request_id}


if __name__ == "__main__":
    unittest.main()
