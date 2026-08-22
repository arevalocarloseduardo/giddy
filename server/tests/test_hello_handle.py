import json
import unittest

from core.handle.helloHandle import HAN_TEXT, WAKEUP_CONFIG, handleHelloMessage


class FakeLogger:
    def bind(self, **_kwargs):
        return self

    def debug(self, _message):
        return None


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)


class HelloHandleTests(unittest.IsolatedAsyncioTestCase):
    def test_wakeup_responses_are_spanish_only(self):
        self.assertTrue(WAKEUP_CONFIG["responses"])
        self.assertTrue(
            all(not HAN_TEXT.search(response) for response in WAKEUP_CONFIG["responses"])
        )

    async def test_preserves_server_output_sample_rate(self):
        websocket = FakeWebSocket()
        conn = type("Connection", (), {})()
        conn.logger = FakeLogger()
        conn.websocket = websocket
        conn.audio_format = None
        conn.welcome_msg = {
            "type": "hello",
            "audio_params": {
                "format": "opus",
                "sample_rate": 24000,
                "channels": 1,
                "frame_duration": 60,
            },
        }

        await handleHelloMessage(conn, {
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            }
        })

        reply = json.loads(websocket.sent[0])
        self.assertEqual(conn.audio_format, "opus")
        self.assertEqual(reply["audio_params"]["sample_rate"], 24000)
        self.assertEqual(conn.welcome_msg["audio_params"]["sample_rate"], 24000)


if __name__ == "__main__":
    unittest.main()
