import unittest

from app.clients.bedrock import _build_converse_payload, _normalize_bedrock_error
from app.config.settings import GuardrailSettings


class FakeBedrockException(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.response = {
            "Error": {
                "Code": code,
                "Message": message,
            }
        }


class BedrockPayloadTests(unittest.TestCase):
    def test_builds_plain_payload_when_guardrails_are_off(self):
        payload = _build_converse_payload(
            target_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
            prompt="hello",
            system_prompt="system text",
            max_tokens=128,
            temperature=0.2,
            guardrail_settings=None,
            request_metadata={"app": "hybrid-ai-assistant"},
        )

        self.assertNotIn("guardrailConfig", payload)
        self.assertEqual(payload["messages"][0]["content"], [{"text": "hello"}])
        self.assertEqual(payload["system"], [{"text": "system text"}])
        self.assertEqual(payload["requestMetadata"], {"app": "hybrid-ai-assistant"})

    def test_builds_user_guardrail_payload(self):
        payload = _build_converse_payload(
            target_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
            prompt="hello",
            system_prompt="system text",
            max_tokens=128,
            temperature=0.2,
            guardrail_settings=GuardrailSettings(
                identifier="gr-123456",
                version="1",
                mode="user",
                trace=True,
            ),
            request_metadata=None,
        )

        self.assertEqual(
            payload["guardrailConfig"],
            {
                "guardrailIdentifier": "gr-123456",
                "guardrailVersion": "1",
                "trace": "enabled",
            },
        )
        self.assertIn("guardContent", payload["messages"][0]["content"][0])
        self.assertEqual(payload["system"], [{"text": "system text"}])

    def test_builds_all_guardrail_payload(self):
        payload = _build_converse_payload(
            target_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
            prompt="hello",
            system_prompt="system text",
            max_tokens=128,
            temperature=0.2,
            guardrail_settings=GuardrailSettings(
                identifier="gr-123456",
                version="1",
                mode="all",
                trace=False,
            ),
            request_metadata=None,
        )

        self.assertIn("guardContent", payload["messages"][0]["content"][0])
        self.assertIn("guardContent", payload["system"][0])
        self.assertNotIn("trace", payload["guardrailConfig"])

    def test_adds_inference_profile_hint_for_on_demand_validation_error(self):
        error = _normalize_bedrock_error(
            FakeBedrockException(
                "ValidationException",
                "Invocation of model ID anthropic.claude-3-5-sonnet-20241022-v2:0 with on-demand throughput isn’t supported.",
            ),
            target_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
            target_kind="model",
        )

        self.assertEqual(error.error_code, "ValidationException")
        self.assertIn("BEDROCK_INFERENCE_PROFILE_ID", str(error))

    def test_adds_quota_hint_for_daily_token_throttling(self):
        error = _normalize_bedrock_error(
            FakeBedrockException(
                "ThrottlingException",
                "Too many tokens per day, please wait before trying again.",
            ),
            target_identifier="us.anthropic.claude-opus-4-6-v1",
            target_kind="inference_profile",
        )

        self.assertEqual(error.error_code, "ThrottlingException")
        self.assertIn("daily token quota", str(error))


if __name__ == "__main__":
    unittest.main()
