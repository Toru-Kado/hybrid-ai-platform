import unittest

from app.clients.bedrock import _build_converse_payload
from app.config.settings import GuardrailSettings


class BedrockPayloadTests(unittest.TestCase):
    def test_builds_plain_payload_when_guardrails_are_off(self):
        payload = _build_converse_payload(
            model_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
            prompt="hello",
            system_prompt="system text",
            max_tokens=128,
            temperature=0.2,
            guardrail_settings=None,
        )

        self.assertNotIn("guardrailConfig", payload)
        self.assertEqual(payload["messages"][0]["content"], [{"text": "hello"}])
        self.assertEqual(payload["system"], [{"text": "system text"}])

    def test_builds_user_guardrail_payload(self):
        payload = _build_converse_payload(
            model_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
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
            model_identifier="anthropic.claude-3-5-sonnet-20241022-v2:0",
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
        )

        self.assertIn("guardContent", payload["messages"][0]["content"][0])
        self.assertIn("guardContent", payload["system"][0])
        self.assertNotIn("trace", payload["guardrailConfig"])


if __name__ == "__main__":
    unittest.main()
