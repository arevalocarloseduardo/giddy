import json
import unittest
from types import SimpleNamespace

from core.handle.intentHandler import handle_user_intent
from core.interaction_modes import (
    CHAT_MODE,
    LISTEN_ONLY_MODE,
    SLEEP_MODE,
    detect_interaction_mode,
    is_wake_only_command,
    voice_output_enabled,
)


class InteractionModeTests(unittest.TestCase):
    def test_dismissal_and_shut_up_enter_sleep(self):
        for phrase in (
            "Callate",
            "Dale Giddy, andate a dormir",
            "No me escuches mas",
            "Chau Giddy",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_interaction_mode(phrase), SLEEP_MODE)

    def test_listen_without_speaking_is_distinct_from_sleep(self):
        for phrase in (
            "Escuchame pero no me hables",
            "Segui escuchando sin hablar",
            "Modo silencioso",
            "No me hables",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_interaction_mode(phrase), LISTEN_ONLY_MODE)

    def test_wake_word_restores_voice_only_from_listen_only(self):
        self.assertEqual(
            detect_interaction_mode("Giddy", LISTEN_ONLY_MODE), CHAT_MODE
        )
        self.assertEqual(
            detect_interaction_mode("Giddy poneme musica", LISTEN_ONLY_MODE),
            CHAT_MODE,
        )
        self.assertIsNone(detect_interaction_mode("Giddy", CHAT_MODE))

    def test_voice_gate_keeps_normal_mode_and_mutes_listen_only(self):
        self.assertTrue(voice_output_enabled(SimpleNamespace()))
        self.assertFalse(
            voice_output_enabled(
                SimpleNamespace(giddy_interaction_mode=LISTEN_ONLY_MODE)
            )
        )

    def test_exact_wake_is_consumed_but_wake_plus_action_is_not(self):
        self.assertTrue(is_wake_only_command("Hey Giddy"))
        self.assertFalse(is_wake_only_command("Giddy poneme musica"))


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send(self, payload):
        self.messages.append(json.loads(payload))


class FakeConnection(SimpleNamespace):
    async def close(self):
        self.closed = True


class InteractionModeFlowTests(unittest.IsolatedAsyncioTestCase):
    def make_connection(self, mode=CHAT_MODE):
        return FakeConnection(
            config={"end_prompt": {}},
            session_id="test-session",
            websocket=FakeWebSocket(),
            giddy_interaction_mode=mode,
            client_abort=True,
            client_is_speaking=False,
            closed=False,
        )

    async def test_listen_only_sends_no_tts_and_keeps_channel_open(self):
        conn = self.make_connection()

        handled = await handle_user_intent(conn, "Escuchame pero no me hables")

        self.assertTrue(handled)
        self.assertFalse(conn.closed)
        self.assertEqual(conn.giddy_interaction_mode, LISTEN_ONLY_MODE)
        self.assertEqual(
            [message["type"] for message in conn.websocket.messages],
            ["stt", "system"],
        )

    async def test_sleep_sends_last_transcript_before_closing_channel(self):
        conn = self.make_connection()

        handled = await handle_user_intent(conn, "Chau Giddy")

        self.assertTrue(handled)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.giddy_interaction_mode, SLEEP_MODE)
        self.assertEqual(
            [message["type"] for message in conn.websocket.messages],
            ["stt", "system"],
        )
        self.assertEqual(conn.websocket.messages[-1]["mode"], SLEEP_MODE)

    async def test_wake_plus_request_restores_voice_without_consuming_request(self):
        conn = self.make_connection(LISTEN_ONLY_MODE)

        handled = await handle_user_intent(conn, "Giddy poneme musica")

        self.assertFalse(handled)
        self.assertEqual(conn.giddy_interaction_mode, CHAT_MODE)
        self.assertEqual(conn.websocket.messages[-1]["mode"], CHAT_MODE)


if __name__ == "__main__":
    unittest.main()
