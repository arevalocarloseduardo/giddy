import hashlib
import os
import time
import uuid
import edge_tts
from datetime import datetime
from pathlib import Path
from core.providers.tts.base import TTSProviderBase
from core.product_settings import ProductSettings


class TTSProvider(TTSProviderBase):
    TTS_PARAM_CONFIG = [
        ("ttsVolume", "volume", -50, 50, 0, int),
        ("ttsRate", "speech_rate", -100, 100, 0, int),
        ("ttsPitch", "pitch_rate", -100, 100, 0, int),
    ]

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        if config.get("private_voice"):
            self.voice = config.get("private_voice")
        else:
            self.voice = config.get("voice")
        self.audio_file_type = config.get("format", "mp3")

        volume = config.get("volume", "0")
        self.volume = int(volume) if volume else 0

        speech_rate = config.get("rate", "0")
        self.speech_rate = int(speech_rate) if speech_rate else 0

        pitch_rate = config.get("pitch", "0")
        self.pitch_rate = int(pitch_rate) if pitch_rate else 0

        # 应用百分比调整
        self._apply_percentage_params(config)

        self.edge_rate = f"{self.speech_rate:+}%"
        self.edge_volume = f"{self.volume:+}%"
        self.edge_pitch = f"{self.pitch_rate:+}Hz"
        self.product_settings = ProductSettings(config.get("settings_path"))
        self.voice_cache_dir = self.product_settings.path.parent / "giddy-voice-cache"
        self.record_voice_metrics = bool(config.get("record_voice_metrics", True))

    def generate_filename(self, extension=".mp3"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        started = time.perf_counter()
        try:
            current = self.product_settings.load()
            product_voice = current.get("voice", {})
            voice = product_voice.get("voice", self.voice)
            speech_rate = int(product_voice.get("rate", self.speech_rate))
            pitch_rate = int(product_voice.get("pitch", self.pitch_rate))
            cacheable = self.product_settings.is_cacheable_voice_text(text, current)
            cache_file = self._cache_file(text, voice, speech_rate, pitch_rate)
            if cacheable:
                cached = self._read_cache(cache_file)
                if cached:
                    self._write_output(output_file, cached)
                    self._record_metric(True, started, text)
                    return None if output_file else cached

            communicate = edge_tts.Communicate(
                text,
                voice=voice,
                rate=f"{speech_rate:+}%",
                volume=self.edge_volume,
                pitch=f"{pitch_rate:+}Hz",
            )
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
            audio_bytes = bytes(audio)
            if not audio_bytes:
                raise RuntimeError("Edge TTS no devolvio audio")
            if cacheable:
                self._store_cache(cache_file, audio_bytes)
            self._write_output(output_file, audio_bytes)
            self._record_metric(False, started, text)
            return None if output_file else audio_bytes
        except Exception as e:
            error_msg = f"Edge TTS请求失败: {e}"
            raise Exception(error_msg)  # 抛出异常，让调用方捕获

    def _cache_file(self, text, voice, speech_rate, pitch_rate):
        identity = "|".join((
            "giddy-voice-v1",
            str(voice),
            str(speech_rate),
            str(pitch_rate),
            self.edge_volume,
            str(text),
        ))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.voice_cache_dir / f"{digest}.mp3"

    @staticmethod
    def _read_cache(path):
        try:
            data = path.read_bytes()
            if len(data) < 100:
                path.unlink(missing_ok=True)
                return None
            path.touch()
            return data
        except OSError:
            return None

    def _store_cache(self, path, audio_bytes):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temp.write_bytes(audio_bytes)
            os.replace(temp, path)
            self._prune_cache()
        except OSError:
            return

    def _prune_cache(self, max_entries=256, max_bytes=25_000_000):
        try:
            entries = sorted(
                self.voice_cache_dir.glob("*.mp3"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            total = 0
            for index, item in enumerate(entries):
                size = item.stat().st_size
                total += size
                if index >= max_entries or total > max_bytes:
                    item.unlink(missing_ok=True)
        except OSError:
            return

    @staticmethod
    def _write_output(output_file, audio_bytes):
        if not output_file:
            return
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio_bytes)

    def _record_metric(self, cache_hit, started, text):
        if not self.record_voice_metrics:
            return
        try:
            self.product_settings.append_voice_metric(
                cache_hit,
                (time.perf_counter() - started) * 1000,
                len(str(text or "")),
            )
        except Exception:
            return
