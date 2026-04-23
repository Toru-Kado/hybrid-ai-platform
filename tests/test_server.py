import json
import os
import tempfile
import textwrap
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from app.clients.base import AssistantResponse
from app.server import create_server


class FakeClient:
    provider_name = "bedrock"
    target_identifier = "us.anthropic.claude-opus-4-6-v1"
    target_kind = "inference_profile"
    target_source = "BEDROCK_INFERENCE_PROFILE_ID"

    def send_message(
        self,
        prompt,
        *,
        system_prompt=None,
        max_tokens=None,
        temperature=None,
        guardrail_settings=None,
    ):
        return AssistantResponse(
            text=f"echo: {prompt}",
            stop_reason="end_turn",
            usage_input_tokens=4,
            usage_output_tokens=3,
            request_id="req-test",
            service_tier=None,
        )


class ServerTests(unittest.TestCase):
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

    def _server_url(self, server) -> str:
        host, port = server.server_address
        return f"http://{host}:{port}"

    def _start_server(self):
        env_path = self._write_env()
        patcher = mock.patch("app.server.create_runtime_client", return_value=FakeClient())
        patcher.start()
        self.addCleanup(patcher.stop)

        server = create_server(
            host="127.0.0.1",
            port=0,
            env_file=env_path,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_health_reports_runtime_target(self):
        server = self._start_server()

        with urllib.request.urlopen(f"{self._server_url(server)}/api/health") as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["provider"], "bedrock")
        self.assertEqual(payload["target_kind"], "inference_profile")
        self.assertEqual(payload["target_source"], "BEDROCK_INFERENCE_PROFILE_ID")

    def test_chat_returns_chat_result(self):
        server = self._start_server()
        body = json.dumps({"prompt": "hello", "max_tokens": 32}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._server_url(server)}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["response_text"], "echo: hello")
        self.assertEqual(payload["provider"], "bedrock")
        self.assertEqual(payload["request_id"], "req-test")

    def test_chat_rejects_missing_prompt(self):
        server = self._start_server()
        body = json.dumps({"prompt": ""}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._server_url(server)}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request)

        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()


if __name__ == "__main__":
    unittest.main()
