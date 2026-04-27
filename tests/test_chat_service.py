import unittest
from types import SimpleNamespace

from app.clients.base import AssistantResponse, AssistantStreamEvent, ConversationTurn
from app.services.chat import (
    ChatService,
    DEFAULT_CONTEXT_WINDOW_MAX_CHARS,
    DEFAULT_CONTEXT_WINDOW_MAX_TURNS,
)


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
        self.calls.append(
            {
                "prompt": prompt,
                "conversation": conversation,
                "system_prompt": system_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
        )
        yield AssistantStreamEvent(type="text_delta", text="hello ")
        yield AssistantStreamEvent(type="text_delta", text="world")
        yield AssistantStreamEvent(
            type="complete",
            response=AssistantResponse(
                text="hello world",
                stop_reason="end_turn",
                usage_input_tokens=1,
                usage_output_tokens=2,
                request_id="req-stream",
                service_tier=None,
            ),
        )


class ChatServiceTests(unittest.TestCase):
    def _service(self, *, max_turns=DEFAULT_CONTEXT_WINDOW_MAX_TURNS, max_chars=DEFAULT_CONTEXT_WINDOW_MAX_CHARS):
        client = FakeClient()
        settings = SimpleNamespace(
            assistant_system_prompt="system prompt",
            aws_region="us-east-1",
            context_window_max_turns=max_turns,
            context_window_max_chars=max_chars,
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
        for index in range(DEFAULT_CONTEXT_WINDOW_MAX_TURNS + 10):
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
        self.assertLessEqual(len(trimmed), DEFAULT_CONTEXT_WINDOW_MAX_TURNS)
        self.assertLessEqual(
            sum(len(turn.content) for turn in trimmed),
            DEFAULT_CONTEXT_WINDOW_MAX_CHARS,
        )
        self.assertEqual(trimmed[0].role, "user")
        self.assertEqual(trimmed[-1].role, "user")
        self.assertTrue(trimmed[-1].content.startswith("latest prompt"))

    def test_uses_configured_context_window_limits_deterministically(self):
        service, client = self._service(max_turns=4, max_chars=80)
        conversation = [
            ConversationTurn(role="assistant", content="orphaned assistant intro"),
            ConversationTurn(role="user", content="older user context that should drop"),
            ConversationTurn(role="assistant", content="older assistant context that should drop"),
            ConversationTurn(role="user", content="recent user question"),
            ConversationTurn(role="assistant", content="recent assistant answer"),
            ConversationTurn(role="user", content="latest prompt"),
        ]

        service.chat(prompt="latest prompt", conversation=conversation)

        trimmed = client.calls[-1]["conversation"]
        self.assertEqual(
            [(turn.role, turn.content) for turn in trimmed],
            [
                ("user", "recent user question"),
                ("assistant", "recent assistant answer"),
                ("user", "latest prompt"),
            ],
        )
        self.assertLessEqual(len(trimmed), 4)
        self.assertLessEqual(sum(len(turn.content) for turn in trimmed), 80)

    def test_stream_chat_yields_text_deltas_and_complete_result(self):
        service, client = self._service()

        events = list(
            service.stream_chat(
                prompt="hello world",
                conversation=[ConversationTurn(role="user", content="hello world")],
            )
        )

        self.assertEqual([event.type for event in events], ["text_delta", "text_delta", "complete"])
        self.assertEqual(events[0].text, "hello ")
        self.assertEqual(events[1].text, "world")
        self.assertEqual(events[-1].result.response_text, "hello world")
        self.assertTrue(client.calls[-1]["stream"])


if __name__ == "__main__":
    unittest.main()
