import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.product_settings import ProductSettings
from core.providers.tts.base import TTSProviderBase
from core.providers.tts.edge import TTSProvider


class FakeCommunication:
    calls = 0
    options = []

    def __init__(self, *args, **kwargs):
        FakeCommunication.calls += 1
        FakeCommunication.options.append(kwargs)

    async def stream(self):
        yield {"type": "audio", "data": b"a" * 256}


class StubTTSProvider(TTSProviderBase):
    async def text_to_speak(self, text, output_file):
        return b""


class EdgeVoiceCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_neutral_volume_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = TTSProvider(
                {
                    "voice": "es-AR-ElenaNeural",
                    "settings_path": str(Path(temp_dir) / "product.json"),
                },
                delete_audio_file=True,
            )

            self.assertEqual(provider.edge_volume, "+0%")

    async def test_uses_live_product_pitch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "product.json"
            ProductSettings(settings_path).save({
                "voice": {
                    "profile": "young",
                    "voice": "es-AR-TomasNeural",
                    "rate": 10,
                    "pitch": 28,
                }
            })
            FakeCommunication.options = []
            with patch("core.providers.tts.edge.edge_tts.Communicate", FakeCommunication):
                provider = TTSProvider(
                    {"voice": "es-AR-ElenaNeural", "settings_path": str(settings_path)},
                    delete_audio_file=True,
                )
                await provider.text_to_speak("Una frase que no usa cache", None)

            self.assertEqual(FakeCommunication.options[-1]["pitch"], "+28Hz")
            self.assertEqual(FakeCommunication.options[-1]["voice"], "es-AR-TomasNeural")

    async def test_reuses_safe_voice_audio_across_provider_instances(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "product.json"
            ProductSettings(settings_path).save({})
            config = {
                "voice": "es-AR-ElenaNeural",
                "rate": 25,
                "settings_path": str(settings_path),
            }
            FakeCommunication.calls = 0
            FakeCommunication.options = []

            with patch(
                "core.providers.tts.edge.edge_tts.Communicate",
                FakeCommunication,
            ):
                first = TTSProvider(config, delete_audio_file=True)
                second = TTSProvider(config, delete_audio_file=True)
                first_audio = await first.text_to_speak("Muy bien", None)
                second_audio = await second.text_to_speak("Muy bien", None)

            self.assertEqual(first_audio, second_audio)
            self.assertEqual(FakeCommunication.calls, 1)
            metrics = ProductSettings(settings_path).metrics_summary()
            self.assertEqual(metrics["voice_requests"], 2)
            self.assertEqual(metrics["voice_cache_hit_share"], 50.0)


class VoiceSegmentationTests(unittest.TestCase):
    def test_splits_spanish_sentences_at_regular_periods(self):
        provider = StubTTSProvider({}, delete_audio_file=True)
        provider.tts_text_buff = ["Muy bien. ¿Vos?"]

        self.assertEqual(provider._get_segment_text(), "Muy bien.")
        self.assertEqual(provider._get_segment_text(), "¿Vos?")

    def test_keeps_short_opening_clause_together_and_preserves_punctuation(self):
        provider = StubTTSProvider({}, delete_audio_file=True)
        provider.tts_text_buff = ["Hola, Carlos. Me alegra escucharte."]

        self.assertEqual(provider._get_segment_text(), "Hola, Carlos.")
        self.assertEqual(provider._get_segment_text(), "Me alegra escucharte.")

    def test_preserves_punctuation_in_final_stream_fragment(self):
        provider = StubTTSProvider({}, delete_audio_file=True)
        provider.tts_text_buff = ["Listo!"]
        spoken = []
        provider.to_tts_stream = lambda text, opus_handler=None: spoken.append(text)

        self.assertTrue(provider._process_remaining_text_stream())
        self.assertEqual(spoken, ["Listo!"])

    def test_cache_allowlist_keeps_safe_punctuation_variants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = ProductSettings(Path(temp_dir) / "product.json")
            settings.save({})

            self.assertTrue(settings.is_cacheable_voice_text("Muy bien"))
            self.assertTrue(settings.is_cacheable_voice_text("¿Vos?"))
            self.assertTrue(
                settings.is_cacheable_voice_text(
                    "Son las catorce y cuarenta y cinco."
                )
            )
            self.assertTrue(
                settings.is_cacheable_voice_text(
                    "Hoy es domingo veintiséis de julio."
                )
            )
            self.assertFalse(settings.is_cacheable_voice_text("Mi clave es 1234"))
            self.assertFalse(
                settings.is_cacheable_voice_text("Son las tres, mi clave es 1234")
            )


if __name__ == "__main__":
    unittest.main()
