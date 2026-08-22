import json
import queue
import unittest
from types import SimpleNamespace

from core.handle.sendAudioHandle import send_stt_message, send_tts_message
from plugins_func.functions.play_music import _open_music_stream


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(json.loads(message))


class MusicEmotionProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_music_tool_explicitly_switches_the_device_scene(self):
        websocket = FakeWebSocket()
        text_queue = queue.Queue()
        conn = SimpleNamespace(
            session_id="session-1",
            sentence_id="sentence-1",
            tts=SimpleNamespace(tts_text_queue=text_queue),
            tts_emotion=None,
            websocket=websocket,
        )

        await _open_music_stream(conn)

        self.assertEqual(websocket.messages[0]["type"], "llm")
        self.assertEqual(websocket.messages[0]["emotion"], "music")
        self.assertEqual(conn.tts_emotion["emotion"], "music")
        self.assertFalse(text_queue.empty())

    async def test_music_intent_marks_first_tts_start_before_tool_runs(self):
        websocket = FakeWebSocket()
        conn = SimpleNamespace(
            config={},
            session_id="session-1",
            sentence_id="sentence-1",
            tts_emotion=None,
            websocket=websocket,
        )

        await send_stt_message(
            conn,
            "Reproduci la noche sin ti.",
            emotion="music",
        )

        self.assertEqual(websocket.messages[0]["type"], "stt")
        self.assertEqual(websocket.messages[1]["state"], "start")
        self.assertEqual(websocket.messages[1]["emotion"], "music")

    async def test_adds_music_emotion_to_matching_tts_stream(self):
        websocket = FakeWebSocket()
        conn = SimpleNamespace(
            session_id="session-1",
            sentence_id="sentence-1",
            tts_emotion={"sentence_id": "sentence-1", "emotion": "music"},
            websocket=websocket,
        )

        await send_tts_message(conn, "start")

        self.assertEqual(websocket.messages[0]["emotion"], "music")

    async def test_does_not_leak_an_old_music_emotion(self):
        websocket = FakeWebSocket()
        conn = SimpleNamespace(
            session_id="session-1",
            sentence_id="sentence-2",
            tts_emotion={"sentence_id": "sentence-1", "emotion": "music"},
            websocket=websocket,
        )

        await send_tts_message(conn, "start")

        self.assertNotIn("emotion", websocket.messages[0])

    async def test_never_sends_chinese_assistant_subtitles(self):
        websocket = FakeWebSocket()
        conn = SimpleNamespace(
            session_id="session-1",
            sentence_id="sentence-1",
            tts_emotion=None,
            websocket=websocket,
        )

        await send_tts_message(conn, "sentence_start", "我在这里哦！")

        self.assertEqual(
            websocket.messages[0]["text"],
            "No te entendi. Decimelo de nuevo.",
        )


if __name__ == "__main__":
    unittest.main()
