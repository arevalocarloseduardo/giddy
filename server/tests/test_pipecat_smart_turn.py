import unittest
from types import SimpleNamespace

import numpy as np

from core.providers.vad.pipecat_smart_turn import PipecatSmartTurn


class PipecatSmartTurnTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = SimpleNamespace()

    async def test_waits_for_minimum_silence_then_accepts_complete_turn(self):
        detector = PipecatSmartTurn(
            {
                "smart_turn_enabled": True,
                "smart_turn_min_silence_ms": 320,
                "smart_turn_fallback_ms": 1600,
                "smart_turn_check_interval_ms": 0,
            },
            predictor=lambda audio: {"prediction": 1, "probability": 0.91},
        )
        detector.append(self.conn, np.ones(512, dtype=np.int16), True)

        self.assertFalse(await detector.evaluate(self.conn, 250))
        self.assertTrue(await detector.evaluate(self.conn, 350))

    async def test_uses_hard_fallback_when_model_keeps_waiting(self):
        detector = PipecatSmartTurn(
            {
                "smart_turn_enabled": True,
                "smart_turn_min_silence_ms": 320,
                "smart_turn_fallback_ms": 900,
                "smart_turn_check_interval_ms": 0,
            },
            predictor=lambda audio: {"prediction": 0, "probability": 0.1},
        )
        detector.append(self.conn, np.ones(512, dtype=np.int16), True)

        self.assertFalse(await detector.evaluate(self.conn, 400))
        self.assertTrue(await detector.evaluate(self.conn, 900))

    async def test_reset_discards_previous_turn_audio(self):
        seen_lengths = []

        def predictor(audio):
            seen_lengths.append(len(audio))
            return {"prediction": 1, "probability": 0.9}

        detector = PipecatSmartTurn(
            {
                "smart_turn_enabled": True,
                "smart_turn_min_silence_ms": 1,
                "smart_turn_check_interval_ms": 0,
            },
            predictor=predictor,
        )
        detector.append(self.conn, np.ones(512, dtype=np.int16), True)
        detector.reset_connection(self.conn)
        detector.append(self.conn, np.ones(512, dtype=np.int16), True)

        self.assertTrue(await detector.evaluate(self.conn, 10))
        self.assertEqual(seen_lengths, [512])


if __name__ == "__main__":
    unittest.main()
