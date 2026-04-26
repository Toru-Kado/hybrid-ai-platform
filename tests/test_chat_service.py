import unittest
from types import SimpleNamespace

from app.clients.base import AssistantResponse, ConversationTurn
from app.services.chat import ChatService, MAX_CONTEXT_CHARS, MAX_CONTEXT_TURNS


class FakeClient:
    provider_name = "bedrock"
    target_identifier = "test-target"
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
            text="ok",
            stop_reason="end_turn",
            usage_input_tokens=1,
            usage_output_tokens=1,
            request_id="req-test",
            service_tier=None,
        )


class ChatServiceTests(unittest.TestCase):
    def _service(self):
        client = FakeClient()
        settings = SimpleNamespace(
            assistant_system_prompt="system prompt",
            aws_region="us-east-1",
        )
        return ChatService(client=client, settings=settings), client

    def test_passes_new_session_turn_through_unchanged(self):
        service, client = self._service()

        service.chat(
            prompt="hello",
            conversation=[ConversationTurn(role="user", content="hello")],
        )

        self.assertEqual(len(client.calls[-1]["conversation"]), 1)
        self.assertEqual(client.calls[-1]["conversation"][0].content, "hello")

    def test_trims_long_running_session_to_recent_context_window(self):
        service, client = self._service()
        conversation = []
        for index in range(MAX_CONTEXT_TURNS + 10):
            conversation.append(
                ConversationTurn(role="user", content=f"user turn {index} " + ("x" * 1200))
            )
            conversation.append(
                ConversationTurn(
                    role="assistant",
                    content=f"assistant turn {index} " + ("y" * 600),
                )
            )
        conversation.append(
            ConversationTurn(role="user", content="latest prompt " + ("z" * 200))
        )

        service.chat(prompt="latest prompt", conversation=conversation)

        trimmed = client.calls[-1]["conversation"]
        self.assertLessEqual(len(trimmed), MAX_CONTEXT_TURNS)
        self.assertLessEqual(sum(len(turn.content) for turn in trimmed), MAX_CONTEXT_CHARS)
        self.assertEqual(trimmed[0].role, "user")
        self.assertEqual(trimmed[-1].role, "user")
        self.assertTrue(trimmed[-1].content.startswith("latest prompt"))


if __name__ == "__main__":
    unittest.main()
