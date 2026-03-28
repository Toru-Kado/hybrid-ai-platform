import os
import tempfile
import textwrap
import unittest
from unittest import mock

from app.config.settings import Settings, SettingsError


class SettingsTests(unittest.TestCase):
    def _write_env(self, body: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", delete=False)
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        handle.write(textwrap.dedent(body).strip() + "\n")
        handle.close()
        return handle.name

    def test_rejects_arn_in_bedrock_model_id(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_MODEL_ID=arn:aws:bedrock:us-east-1:123456789012:guardrail/gr-123456
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env(env_path)

    def test_guardrail_identifier_requires_version(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
            BEDROCK_GUARDRAIL_IDENTIFIER=gr-123456
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env(env_path)

    def test_guardrail_mode_defaults_to_user_when_guardrail_is_configured(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
            BEDROCK_GUARDRAIL_IDENTIFIER=gr-123456
            BEDROCK_GUARDRAIL_VERSION=1
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env(env_path)

        self.assertEqual(settings.bedrock_guardrail_mode, "user")
        self.assertIsNotNone(settings.resolve_guardrail_settings())

    def test_guardrail_mode_override_requires_guardrail_config(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env(env_path)
            with self.assertRaises(SettingsError):
                settings.resolve_guardrail_settings("user")

    def test_accepts_inference_profile_id_as_runtime_target(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_INFERENCE_PROFILE_ID=us.anthropic.claude-opus-4-6-v1
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env(env_path)

        self.assertEqual(
            settings.runtime_target.identifier, "us.anthropic.claude-opus-4-6-v1"
        )
        self.assertEqual(settings.runtime_target.kind, "inference_profile")
        self.assertEqual(
            settings.runtime_target.source_env, "BEDROCK_INFERENCE_PROFILE_ID"
        )

    def test_rejects_inference_profile_id_and_arn_together(self):
        env_path = self._write_env(
            """
            AWS_REGION=us-east-1
            BEDROCK_INFERENCE_PROFILE_ID=us.anthropic.claude-opus-4-6-v1
            BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-opus-4-6-v1
            """
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SettingsError):
                Settings.from_env(env_path)


if __name__ == "__main__":
    unittest.main()
