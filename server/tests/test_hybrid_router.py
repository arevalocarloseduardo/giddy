import unittest
import tempfile
from pathlib import Path

from core.providers.llm.hybrid.hybrid import GiddyRouter, LLMProvider


class GiddyRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = GiddyRouter()

    def test_routes_small_talk_locally(self):
        cases = [
            "Hola",
            "Como estas?",
            "Contame un chiste corto",
            "Que significa efimero?",
            "Gracias, genial",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(self.router.choose(text, "balanced").route, "local")

    def test_routes_actions_and_current_data_to_hermes(self):
        cases = [
            "Agendame una reunion mañana",
            "Busca el clima de hoy",
            "Analiza mis ventas y arma un PDF",
            "Mandale un WhatsApp a Carla",
            "Cuanto es 831 dividido 17?",
            "Te acordas cuanto gaste en mi negocio?",
            "Ayudame a decidir entre dos propuestas",
            "Revisa este contrato y evalua los riesgos",
            "Como optimizo las finanzas del negocio?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual(self.router.choose(text, "balanced").route, "power")

    def test_modes_change_ambiguous_requests(self):
        text = "Explicame por que el cielo es azul"
        self.assertEqual(self.router.choose(text, "eco").route, "local")
        self.assertEqual(self.router.choose(text, "max").route, "power")

    def test_explicit_choice_wins(self):
        self.assertEqual(self.router.choose("Usa local y saludame", "max").route, "local")
        self.assertEqual(self.router.choose("Usa Hermes y pensalo bien", "eco").route, "power")

    def test_trims_dialogue_to_budget_and_preserves_latest_message(self):
        dialogue = [
            {"role": "system", "content": "s" * 200},
            {"role": "user", "content": "old" * 100},
            {"role": "assistant", "content": "middle" * 50},
            {"role": "user", "content": "LATEST"},
        ]
        trimmed = LLMProvider._trim_dialogue(dialogue, 100, keep_system=False)

        self.assertEqual(trimmed[-1]["content"], "LATEST")
        self.assertLessEqual(sum(len(item["content"]) for item in trimmed), 100)

    def test_sanitizes_unpronounceable_local_output(self):
        raw = "żTodo bien?Ą Si—claro… \U0001f600\n"
        self.assertEqual(
            LLMProvider._sanitize_spoken_text(raw),
            "¿Todo bien?¡ Si, claro...  ",
        )

    def test_uses_curated_zero_token_entertainment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = object.__new__(LLMProvider)
            provider.router = self.router
            from core.product_settings import ProductSettings
            provider.settings = ProductSettings(Path(temp_dir) / "product.json")
            requests = (
                "Contame un chiste corto",
                "Decime un acertijo corto",
                "Contame una historia corta",
            )
            for index, request in enumerate(requests):
                with self.subTest(request=request):
                    decision = self.router.choose(request, "balanced")
                    answer = provider._safe_entertainment_response(
                        f"session-{index}", request, decision
                    )
                    self.assertEqual(decision.reason, "entretenimiento breve")
                    self.assertTrue(answer)
                    self.assertNotIn("gordo", answer.lower())
            metric = provider.settings.metrics_path.read_text(encoding="utf-8")
            self.assertIn('"prompt_tokens": 0', metric)

    def test_falls_back_to_hermes_when_local_ai_is_unavailable(self):
        class FakePower:
            def response(self, session_id, dialogue, **kwargs):
                yield "respaldo listo"

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "product.json"
            from core.product_settings import ProductSettings
            settings = ProductSettings(settings_path)
            settings.save({
                "routing": {"local_url": "http://127.0.0.1:9"},
                "experience": {
                    "instant_enabled": False,
                    "thinking_cue_enabled": False,
                },
            })
            provider = LLMProvider({
                "settings_path": str(settings_path),
                "power": {
                    "model_name": "giddy",
                    "url": "http://127.0.0.1:1/v1",
                    "api_key": "test-key",
                },
            })
            provider.power = FakePower()

            answer = "".join(provider.response(
                "session-fallback",
                [{"role": "user", "content": "Hola"}],
            ))

            self.assertEqual(answer, "respaldo listo")
            events = provider.settings.metrics_path.read_text(encoding="utf-8")
            self.assertIn('"fallback": true', events)
            self.assertIn('"reason": "respaldo automatico"', events)

    def test_speaks_a_short_cue_before_power_work(self):
        class FakePower:
            def response(self, session_id, dialogue, **kwargs):
                yield "resultado listo"

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "product.json"
            provider = LLMProvider({
                "settings_path": str(settings_path),
                "power": {
                    "model_name": "giddy",
                    "url": "http://127.0.0.1:1/v1",
                    "api_key": "test-key",
                },
            })
            provider.power = FakePower()

            answer = "".join(provider.response(
                "session-power",
                [{"role": "user", "content": "Busca el clima de hoy"}],
            ))
            immediate_follow_up = "".join(provider.response(
                "session-power",
                [{"role": "user", "content": "Busca el clima de manana"}],
            ))

            self.assertEqual(answer, "Dame un segundo. resultado listo")
            self.assertEqual(immediate_follow_up, "resultado listo")
            events = provider.settings.metrics_path.read_text(encoding="utf-8")
            self.assertIn('"cue": true', events)

    def test_speaks_a_cached_acknowledgement_before_local_model_work(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "product.json"
            provider = LLMProvider({
                "settings_path": str(settings_path),
                "power": {
                    "model_name": "giddy",
                    "url": "http://127.0.0.1:1/v1",
                    "api_key": "test-key",
                },
            })
            provider._local_response = lambda *args, **kwargs: iter(["respuesta local"])

            answer = "".join(provider.response(
                "session-local-cue",
                [{"role": "user", "content": "Me gusta tomar mate a la tarde"}],
            ))

            self.assertEqual(answer, "respuesta local")


if __name__ == "__main__":
    unittest.main()
