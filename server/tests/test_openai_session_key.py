import unittest
from unittest.mock import patch

from core.providers.llm.openai import openai as provider_module


class OpenAISessionKeyTests(unittest.TestCase):
    def _build_provider(self, **overrides):
        config = {
            "model_name": "giddy",
            "api_key": "test-api-key",
            "url": "http://127.0.0.1:8664/v1",
        }
        config.update(overrides)
        with (
            patch.object(provider_module, "check_model_key", return_value=None),
            patch.object(provider_module.openai, "OpenAI") as openai_client,
        ):
            provider_module.LLMProvider(config)
        return openai_client.call_args.kwargs

    def test_configures_stable_hermes_session_header(self):
        kwargs = self._build_provider(session_key="giddy-device-primary")

        self.assertEqual(
            kwargs["default_headers"],
            {"X-Hermes-Session-Key": "giddy-device-primary"},
        )

    def test_omits_header_for_regular_openai_providers(self):
        kwargs = self._build_provider()

        self.assertNotIn("default_headers", kwargs)


if __name__ == "__main__":
    unittest.main()
