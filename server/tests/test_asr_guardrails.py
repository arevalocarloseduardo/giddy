import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType
from core.providers.asr.openai import ASRProvider


class CapturingASR(ASRProviderBase):
    def __init__(self):
        self.interface_type = InterfaceType.NON_STREAM
        self.captured = []

    async def handle_voice_stop(self, conn, asr_audio_task):
        self.captured.append(asr_audio_task)
        return True

    async def speech_to_text(self, opus_data, session_id, artifacts=None):
        return "", None


class RejectingASR(CapturingASR):
    async def handle_voice_stop(self, conn, asr_audio_task):
        self.captured.append(asr_audio_task)
        return False


class FakeConnection:
    def __init__(self, provider):
        self.config = {"max_voice_command_seconds": 3}
        self.client_listen_mode = "auto"
        self.client_have_voice = True
        self.client_voice_stop = False
        self.asr_audio = []
        self.asr_audio_bytes = 0
        self.asr = provider
        self.close_after_chat = False
        self.closed = False

    def reset_audio_states(self):
        self.asr_audio.clear()
        self.asr_audio_bytes = 0
        self.client_voice_stop = False

    async def close(self):
        self.closed = True


class ASRGuardrailTests(unittest.IsolatedAsyncioTestCase):
    def _provider(self):
        temp_dir = tempfile.mkdtemp()
        return ASRProvider(
            {
                "api_key": "test",
                "base_url": "http://127.0.0.1:9000/v1/audio/transcriptions",
                "model_name": "whisper-1",
                "language": "es",
                "prompt": "Clima de hoy en La Plata.",
                "hotwords": "clima temperatura grados La Plata",
                "output_dir": temp_dir,
                "max_transcript_chars": 100,
                "max_transcript_words": 20,
            },
            delete_audio_file=True,
        )

    def test_discards_known_silence_hallucination(self):
        provider = self._provider()
        text = "Subtitulos realizados por la comunidad de Amara.org"
        self.assertEqual(provider._sanitize_transcript(text), "")

    def test_preserves_short_spanish_command(self):
        provider = self._provider()
        text = "Poneme Nuestro Sueno de Grupo Niche"
        self.assertEqual(provider._sanitize_transcript(text), text)

    def test_discards_long_background_transcript(self):
        provider = self._provider()
        text = " ".join(["comentario"] * 21)
        self.assertEqual(provider._sanitize_transcript(text), "")

    async def test_sends_spanish_context_and_hotwords_to_local_stt(self):
        provider = self._provider()
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            artifacts = SimpleNamespace(file_path=audio.name)
            response = SimpleNamespace(
                status_code=200,
                text='{"text":"Clima de hoy"}',
                json=lambda: {"text": "Clima de hoy"},
            )
            with patch.object(provider, "_post_audio", return_value=response) as post:
                text, _ = await provider.speech_to_text([], "session", artifacts)

        data = post.call_args.args[1]
        self.assertEqual(text, "Clima de hoy")
        self.assertEqual(data["prompt"], "Clima de hoy en La Plata.")
        self.assertIn("temperatura", data["hotwords"])

    async def test_forces_recognition_at_audio_time_limit(self):
        provider = CapturingASR()
        conn = FakeConnection(provider)
        pcm = b"\x00\x00" * (16000 * 3)

        await provider.receive_audio(conn, pcm, audio_have_voice=True)

        self.assertEqual(len(provider.captured), 1)
        self.assertEqual(provider.captured[0], [pcm])
        self.assertEqual(conn.asr_audio, [])
        self.assertEqual(conn.asr_audio_bytes, 0)
        self.assertTrue(conn.close_after_chat)
        self.assertFalse(conn.closed)

    async def test_closes_long_turn_when_recognition_is_rejected(self):
        provider = RejectingASR()
        conn = FakeConnection(provider)
        pcm = b"\x00\x00" * (16000 * 3)

        await provider.receive_audio(conn, pcm, audio_have_voice=True)

        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
