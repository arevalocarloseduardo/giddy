import json
import tempfile
import unittest
from pathlib import Path

from core.product_settings import ProductSettings


class ProductSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = ProductSettings(Path(self.temp_dir.name) / "product.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_stable_setup_token(self):
        first = self.settings.setup_token()
        second = self.settings.setup_token()

        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 24)

    def test_validates_and_persists_public_settings(self):
        saved = self.settings.save({
            "mode": "eco",
            "voice": {"profile": "invalid", "rate": 999, "pitch": -999, "voice": "invalid"},
            "routing": {"local_max_tokens": 12, "power_max_tokens": 9999},
        })

        self.assertEqual(saved["mode"], "eco")
        self.assertEqual(saved["voice"]["rate"], 40)
        self.assertEqual(saved["voice"]["pitch"], -50)
        self.assertEqual(saved["voice"]["profile"], "robot")
        self.assertEqual(saved["voice"]["voice"], "es-AR-TomasNeural")
        self.assertEqual(saved["routing"]["local_max_tokens"], 32)
        self.assertEqual(saved["routing"]["power_max_tokens"], 1000)
        self.assertEqual(json.loads(self.settings.path.read_text())["mode"], "eco")

    def test_summarizes_local_savings_without_storing_raw_text(self):
        self.settings.append_route_metric({
            "route": "local",
            "reason": "saludo",
            "input_chars": 120,
            "output_chars": 40,
            "prompt_tokens": 30,
            "output_tokens": 10,
            "session_id": "private-session",
        })
        self.settings.append_route_metric({"route": "power", "reason": "accion real"})

        summary = self.settings.metrics_summary()
        raw = self.settings.metrics_path.read_text()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["local_share"], 50.0)
        self.assertEqual(summary["estimated_api_tokens_saved"], 40)
        self.assertNotIn("private-session", raw)

    def test_resolves_quick_actions_from_live_settings(self):
        saved = self.settings.save({
            "quick_actions": [
                {"id": "agenda", "label": "Mi dia", "prompt": "Resume mi agenda"},
            ]
        })

        self.assertEqual(saved["quick_actions"][0]["label"], "Mi dia")
        self.assertEqual(
            self.settings.resolve_quick_action("agenda")["prompt"],
            "Resume mi agenda",
        )
        self.assertIsNone(self.settings.resolve_quick_action("missing"))

    def test_migrates_old_local_cue_without_affecting_thinking_cue(self):
        saved = self.settings.save({
            "schema_version": 2,
            "experience": {
                "local_cue": "A ver.",
                "thinking_cue": "Dame un segundo.",
            },
        })

        self.assertEqual(saved["schema_version"], 4)
        self.assertEqual(saved["experience"]["local_cue"], "")
        self.assertEqual(
            saved["experience"]["thinking_cue"], "Dame un segundo."
        )


if __name__ == "__main__":
    unittest.main()
