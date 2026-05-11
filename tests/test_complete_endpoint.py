import json
import os
import tempfile
import textwrap
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from app.clients import AssistantClientError
from app.clients.base import AssistantResponse
from app.server import create_server


class FakeCompletionClient:
    provider_name = "bedrock"
    target_identifier = "us.anthropic.claude-opus-4-6-v1"
    target_kind = "inference_profile"
    target_source = "BEDROCK_INFERENCE_PROFILE_ID"

    def __init__(self) -> None:
        self.calls = []

    def send_message(
        self,
        prompt,
        *,
        conversation=None,
        system_prompt=None,
        max_tokens=None,
        temperature=None,
        guardrail_settings=None,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "conversation": conversation,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return AssistantResponse(
            text="configure my AWS credentials?",
            stop_reason="end_turn",
            usage_input_tokens=10,
            usage_output_tokens=5,
            request_id="req-complete",
            service_tier=None,
        )

    def stream_message(self, prompt, **kwargs):
        yield from ()


class CompleteEndpointTests(unittest.TestCase):
    def _write_env(self) -> str:
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        handle.write(
            textwrap.dedent(
                """
                APP_NAME=hybrid-ai-assistant-test
                AI_PROVIDER=bedrock
                AWS_REGION=us-east-1
                BEDROCK_INFERENCE_PROFILE_ID=us.anthropic.claude-opus-4-6-v1
                BEDROCK_GUARDRAIL_MODE=off
                """
            ).strip()
            + "\n"
        )
        handle.close()
        return handle.name

    def _write_db_path(self) -> str:
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def _server_url(self, server) -> str:
        host, port = server.server_address
        return f"http://{host}:{port}"

    def _json_request(self, url: str, *, method: str = "GET", payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def _start_server(self, client=None):
        env_path = self._write_env()
        db_path = self._write_db_path()
        fake_client = client or FakeCompletionClient()
        patcher = mock.patch("app.server.create_runtime_client", return_value=fake_client)
        patcher.start()
        self.addCleanup(patcher.stop)

        server = create_server(
            host="127.0.0.1",
            port=0,
            env_file=env_path,
            db_path=db_path,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, fake_client

    def test_complete_returns_completion_text(self):
        server, client = self._start_server()
        result = self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "How do I"},
        )

        self.assertEqual(result["completion"], "configure my AWS credentials?")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["prompt"], "How do I")
        self.assertIsNone(client.calls[0]["conversation"])
        self.assertIn("keystroke prediction", client.calls[0]["system_prompt"])

    def test_complete_uses_default_max_tokens(self):
        server, client = self._start_server()
        self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "Write a function"},
        )

        self.assertEqual(client.calls[0]["max_tokens"], 50)

    def test_complete_caps_max_tokens_at_60(self):
        server, client = self._start_server()
        self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "Write a function", "max_tokens": 200},
        )

        self.assertEqual(client.calls[0]["max_tokens"], 60)

    def test_complete_returns_empty_for_short_text(self):
        server, client = self._start_server()
        result = self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "Hi"},
        )

        self.assertEqual(result["completion"], "")
        self.assertEqual(len(client.calls), 0)

    def test_complete_returns_400_for_missing_text(self):
        server, _client = self._start_server()

        with self.assertRaises(urllib.error.HTTPError) as raised:
            self._json_request(
                f"{self._server_url(server)}/api/complete",
                method="POST",
                payload={"max_tokens": 50},
            )

        self.assertEqual(raised.exception.code, 400)

    def test_complete_returns_empty_on_provider_error(self):
        fake_client = FakeCompletionClient()
        fake_client.send_message = mock.Mock(
            side_effect=AssistantClientError("provider failed", error_code="Boom")
        )
        server, _client = self._start_server(fake_client)
        result = self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "How do I"},
        )

        self.assertEqual(result["completion"], "")

    def test_complete_does_not_persist_to_session_store(self):
        server, _client = self._start_server()
        self._json_request(
            f"{self._server_url(server)}/api/complete",
            method="POST",
            payload={"text": "How do I"},
        )

        sessions = self._json_request(f"{self._server_url(server)}/api/sessions")
        self.assertEqual(sessions["sessions"], [])


if __name__ == "__main__":
    unittest.main()
