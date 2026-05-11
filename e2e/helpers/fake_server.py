"""Standalone fake server for E2E/integration tests.

Starts the real Python HTTP server with a FakeClient that echoes prompts,
using an OS-assigned port (or specified port) and isolated temp database.
Prints READY:<port> to stdout so the Playwright fixture can discover the port.
"""

import argparse
import sys
import tempfile
import textwrap
from unittest import mock

from app.clients.base import AssistantResponse, AssistantStreamEvent
from app.server import create_server


class FakeClient:
    """Deterministic AI client that echoes prompts for testing."""

    provider_name = "bedrock"
    target_identifier = "us.anthropic.claude-opus-4-6-v1"
    target_kind = "inference_profile"
    target_source = "BEDROCK_INFERENCE_PROFILE_ID"

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
        return AssistantResponse(
            text=f"echo: {prompt}",
            stop_reason="end_turn",
            usage_input_tokens=4,
            usage_output_tokens=3,
            request_id="req-fake",
            service_tier=None,
        )

    def stream_message(
        self,
        prompt,
        *,
        conversation=None,
        system_prompt=None,
        max_tokens=None,
        temperature=None,
        guardrail_settings=None,
    ):
        words = prompt.split()
        for i, word in enumerate(words):
            text = word if i == 0 else f" {word}"
            yield AssistantStreamEvent(type="text_delta", text=text)
        yield AssistantStreamEvent(
            type="complete",
            response=AssistantResponse(
                text=f"echo: {prompt}",
                stop_reason="end_turn",
                usage_input_tokens=4,
                usage_output_tokens=len(words),
                request_id="req-fake-stream",
                service_tier=None,
            ),
        )


def main():
    parser = argparse.ArgumentParser(description="Fake API server for E2E tests")
    parser.add_argument("--port", type=int, default=0, help="Port to bind (0 = OS-assigned)")
    args = parser.parse_args()

    # Write a minimal env file
    env_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False
    )
    env_file.write(
        textwrap.dedent("""\
            APP_NAME=hybrid-ai-assistant-e2e
            AI_PROVIDER=bedrock
            AWS_REGION=us-east-1
            BEDROCK_INFERENCE_PROFILE_ID=us.anthropic.claude-opus-4-6-v1
            BEDROCK_GUARDRAIL_MODE=off
        """)
    )
    env_file.close()

    # Isolated database
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()

    with mock.patch("app.server.create_runtime_client", return_value=FakeClient()):
        server = create_server(
            host="127.0.0.1",
            port=args.port,
            env_file=env_file.name,
            db_path=db_file.name,
        )

    _host, port = server.server_address
    print(f"READY:{port}", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
