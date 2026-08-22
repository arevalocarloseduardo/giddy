import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.product_settings import ProductSettings
from core.providers.llm.hybrid.reflex import ReflexEngine


class ReflexEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = ProductSettings(Path(self.temp_dir.name) / "product.json")
        self.engine = ReflexEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_answers_common_phrases_without_a_model(self):
        current = self.settings.load()

        reply = self.engine.match("Hola, ¿cómo estás?", current)

        self.assertEqual(reply.text, "Muy bien. ¿Vos?")
        self.assertEqual(reply.reason, "respuesta instantánea")

    def test_answers_time_and_date_locally(self):
        current = self.settings.load()
        now = datetime(2026, 7, 26, 14, 5, tzinfo=timezone.utc)

        time_reply = self.engine.match("¿Qué hora es?", current, now=now)
        date_reply = self.engine.match("¿Qué día es hoy?", current, now=now)

        self.assertEqual(time_reply.text, "Son las catorce y cinco.")
        self.assertEqual(date_reply.text, "Hoy es domingo veintiséis de julio.")

    def test_uses_live_custom_responses_and_can_be_disabled(self):
        custom = self.settings.save({
            "experience": {
                "instant_responses": [
                    {
                        "id": "custom",
                        "triggers": ["modo rapido"],
                        "response": "Listo al instante.",
                    }
                ]
            }
        })
        self.assertEqual(
            self.engine.match("Modo rápido", custom).text,
            "Listo al instante.",
        )

        disabled = self.settings.save({"experience": {"instant_enabled": False}})
        self.assertIsNone(self.engine.match("Modo rápido", disabled))


if __name__ == "__main__":
    unittest.main()
