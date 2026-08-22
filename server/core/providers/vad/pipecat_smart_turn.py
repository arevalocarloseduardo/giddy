import asyncio
import threading
import time
from collections import deque

import numpy as np

from config.logger import setup_logging


TAG = __name__
logger = setup_logging()


class PipecatSmartTurn:
    """Shared Pipecat predictor with lightweight audio state per connection."""

    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 512
    MAX_AUDIO_SECONDS = 8.5

    def __init__(self, config, predictor=None):
        self.enabled = self._as_bool(config.get("smart_turn_enabled", True))
        self.min_silence_ms = int(config.get("smart_turn_min_silence_ms", 320))
        self.fallback_ms = int(config.get("smart_turn_fallback_ms", 1600))
        self.check_interval_ms = int(config.get("smart_turn_check_interval_ms", 360))
        self.cpu_count = max(1, int(config.get("smart_turn_cpu_count", 1)))
        self._predictor = predictor
        self._model = None
        self._load_error = None
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()
        self._max_chunks = int(
            self.MAX_AUDIO_SECONDS * self.SAMPLE_RATE / self.CHUNK_SAMPLES
        )

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off", ""}

    @property
    def available(self):
        if not self.enabled:
            return False
        if self._predictor is not None:
            return True
        return self._ensure_model()

    @property
    def load_error(self):
        return self._load_error

    def _ensure_model(self):
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        with self._load_lock:
            if self._model is not None:
                return True
            if self._load_error is not None:
                return False
            try:
                from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
                    LocalSmartTurnAnalyzerV3,
                )

                self._model = LocalSmartTurnAnalyzerV3(
                    sample_rate=self.SAMPLE_RATE,
                    cpu_count=self.cpu_count,
                )
                logger.bind(tag=TAG).info(
                    "Pipecat Smart Turn v3 activo (modelo local compartido)"
                )
                return True
            except Exception as exc:
                self._load_error = exc
                logger.bind(tag=TAG).warning(
                    "Pipecat Smart Turn no disponible; se usa silencio clasico: {}",
                    exc,
                )
                return False

    def _state(self, conn):
        state = getattr(conn, "_pipecat_turn_state", None)
        if state is None:
            state = {
                "audio": deque(maxlen=self._max_chunks),
                "last_check_ms": 0.0,
                "speech_seen": False,
            }
            conn._pipecat_turn_state = state
        return state

    def append(self, conn, audio_int16, is_speech):
        if not self.enabled:
            return
        state = self._state(conn)
        state["audio"].append(np.asarray(audio_int16, dtype=np.int16).copy())
        if is_speech:
            state["speech_seen"] = True
            state["last_check_ms"] = 0.0

    async def evaluate(self, conn, silence_ms):
        if not self.available:
            return None

        state = self._state(conn)
        if not state["speech_seen"] or silence_ms < self.min_silence_ms:
            return False
        if silence_ms >= self.fallback_ms:
            return True

        now_ms = time.monotonic() * 1000
        if now_ms - state["last_check_ms"] < self.check_interval_ms:
            return False
        state["last_check_ms"] = now_ms

        chunks = tuple(state["audio"])
        if not chunks:
            return False
        audio = np.concatenate(chunks).astype(np.float32) / 32768.0
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._predict_audio, audio)
        except Exception as exc:
            logger.bind(tag=TAG).warning(
                "Fallo Pipecat Smart Turn; esperando fallback: {}", exc
            )
            return silence_ms >= self.fallback_ms

        complete = bool(result.get("prediction"))
        logger.bind(tag=TAG).debug(
            "Smart Turn complete={} prob={:.3f} silencio={}ms inferencia={:.1f}ms",
            complete,
            float(result.get("probability", 0.0)),
            int(silence_ms),
            (time.perf_counter() - started) * 1000,
        )
        return complete

    def _predict_audio(self, audio):
        with self._predict_lock:
            if self._predictor is not None:
                return self._predictor(audio)
            # Pipecat does not expose a stateless prediction method. This small
            # adapter isolates that API detail while keeping one ONNX model in RAM.
            return self._model._predict_endpoint(audio)

    def reset_connection(self, conn):
        state = getattr(conn, "_pipecat_turn_state", None)
        if state is not None:
            state["audio"].clear()
            state["last_check_ms"] = 0.0
            state["speech_seen"] = False

    def release_connection(self, conn):
        if hasattr(conn, "_pipecat_turn_state"):
            delattr(conn, "_pipecat_turn_state")
