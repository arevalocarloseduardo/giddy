import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.interaction_guard import (
    audio_block_reason,
    begin_exclusive_operation,
    discard_blocked_audio,
    end_exclusive_operation,
)


class InteractionGuardTests(unittest.TestCase):
    def _connection(self):
        return SimpleNamespace(
            client_is_speaking=False,
            client_aec=False,
            giddy_exclusive_operation=None,
            giddy_ignore_audio_until=0.0,
            giddy_last_audio_block_log_at=0.0,
            reset_audio_states=Mock(),
            logger=Mock(),
        )

    def test_blocks_audio_during_an_exclusive_operation(self):
        conn = self._connection()

        self.assertTrue(begin_exclusive_operation(conn, "generate_image"))
        self.assertIn("generate_image", audio_block_reason(conn))
        self.assertTrue(discard_blocked_audio(conn, "test"))
        conn.reset_audio_states.assert_called_once_with()

    def test_keeps_a_short_audio_cooldown_after_the_operation(self):
        conn = self._connection()
        begin_exclusive_operation(conn, "generate_image")

        end_exclusive_operation(conn, "generate_image", cooldown_seconds=2.0)

        self.assertIsNone(conn.giddy_exclusive_operation)
        self.assertGreater(conn.giddy_ignore_audio_until, time.monotonic())
        self.assertEqual(audio_block_reason(conn), "enfriamiento de audio")

    def test_discards_echo_while_speaking_without_aec(self):
        conn = self._connection()
        conn.client_is_speaking = True

        self.assertEqual(
            audio_block_reason(conn),
            "reproduccion sin cancelacion de eco",
        )

        conn.client_aec = True
        self.assertIsNone(audio_block_reason(conn))


if __name__ == "__main__":
    unittest.main()
