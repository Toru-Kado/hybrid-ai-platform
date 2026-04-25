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

    def _start_server(self):
        env_path = self._write_env()
        db_path = self._write_db_path()
        fake_client = FakeClient()
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

    def test_health_reports_runtime_target(self):
        server, _client = self._start_server()
        payload = self._json_request(f"{self._server_url(server)}/api/health")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["provider"], "bedrock")
        self.assertEqual(payload["target_kind"], "inference_profile")
        self.assertEqual(payload["target_source"], "BEDROCK_INFERENCE_PROFILE_ID")

    def test_chat_returns_chat_result_and_session(self):
        server, _client = self._start_server()
        payload = self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "hello", "max_tokens": 32},
        )

        self.assertEqual(payload["response_text"], "echo: hello")
        self.assertEqual(payload["provider"], "bedrock")
        self.assertEqual(payload["request_id"], "req-test")
        self.assertEqual(payload["session"]["message_count"], 2)
        self.assertEqual(payload["message"]["role"], "assistant")

    def test_chat_persists_messages_to_session_history(self):
        server, fake_client = self._start_server()
        created = self._json_request(
            f"{self._server_url(server)}/api/sessions",
            method="POST",
            payload={"title": "Scratchpad"},
        )
        session_id = created["session"]["session_id"]

        self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "hello history", "session_id": session_id},
        )
        payload = self._json_request(f"{self._server_url(server)}/api/sessions/{session_id}")

        self.assertEqual(payload["session"]["session_id"], session_id)
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"], "hello history")
        self.assertEqual(payload["messages"][1]["role"], "assistant")
        self.assertEqual(payload["messages"][1]["content"], "echo: hello history")
        self.assertEqual(len(fake_client.calls[-1]["conversation"]), 1)
        self.assertEqual(fake_client.calls[-1]["conversation"][0].content, "hello history")

    def test_chat_sends_full_history_to_runtime_client(self):
        server, fake_client = self._start_server()
        first = self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "first question"},
        )
        session_id = first["session"]["session_id"]

        self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "follow up", "session_id": session_id},
        )

        conversation = fake_client.calls[-1]["conversation"]
        self.assertEqual([turn.role for turn in conversation], ["user", "assistant", "user"])
        self.assertEqual(
            [turn.content for turn in conversation],
            ["first question", "echo: first question", "follow up"],
        )

    def test_sessions_list_returns_newest_first(self):
        server, _client = self._start_server()
        self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "first session"},
        )
        self._json_request(
            f"{self._server_url(server)}/api/chat",
            method="POST",
            payload={"prompt": "second session"},
        )
        payload = self._json_request(f"{self._server_url(server)}/api/sessions")

        self.assertEqual(len(payload["sessions"]), 2)
        self.assertEqual(payload["sessions"][0]["title"], "second session")
        self.assertEqual(payload["sessions"][1]["title"], "first session")

    def test_chat_rejects_missing_prompt(self):
        server, _client = self._start_server()
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
