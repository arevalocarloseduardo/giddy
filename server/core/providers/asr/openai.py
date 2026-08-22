import asyncio
import os
import re
import time
import unicodedata
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.providers.asr.dto.dto import InterfaceType
from core.providers.asr.base import ASRProviderBase

import requests

TAG = __name__
logger = setup_logging()

class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        self.interface_type = InterfaceType.NON_STREAM
        self.api_key = config.get("api_key")
        self.api_url = config.get("base_url")
        self.model = config.get("model_name")
        self.language = config.get("language")  # hint de idioma opcional (ej. "es")
        self.prompt = str(config.get("prompt", "")).strip()
        self.hotwords = str(config.get("hotwords", "")).strip()
        self.output_dir = config.get("output_dir")
        self.delete_audio_file = delete_audio_file
        self.timeout_seconds = max(3, int(config.get("timeout_seconds", 15)))
        self.max_transcript_chars = max(
            80, int(config.get("max_transcript_chars", 260))
        )
        self.max_transcript_words = max(
            12, int(config.get("max_transcript_words", 42))
        )

        os.makedirs(self.output_dir, exist_ok=True)

    def requires_file(self) -> bool:
        return True

    @staticmethod
    def _normalized_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text or "")
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        return re.sub(r"\s+", " ", normalized).strip().lower()

    def _sanitize_transcript(self, text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "")).strip()
        normalized = self._normalized_text(text)
        known_hallucinations = (
            "subtitulos realizados por la comunidad de amara.org",
            "subtitulos por la comunidad de amara.org",
            "gracias por ver el video",
        )
        if any(phrase in normalized for phrase in known_hallucinations):
            logger.bind(tag=TAG).warning(
                f"Transcripcion de silencio descartada: {text}"
            )
            return ""

        words = re.findall(r"[a-z0-9]+", normalized)
        if len(text) > self.max_transcript_chars or len(words) > self.max_transcript_words:
            logger.bind(tag=TAG).warning(
                f"Audio ambiente descartado por longitud: {len(text)} caracteres, "
                f"{len(words)} palabras"
            )
            return ""

        if len(words) >= 6:
            most_repeated = max(
                (words.count(word) for word in set(words)), default=0
            )
            if most_repeated >= 4 and most_repeated / len(words) >= 0.45:
                logger.bind(tag=TAG).warning(
                    f"Transcripcion repetitiva descartada: {text}"
                )
                return ""
        return text

    def _post_audio(self, file_path: str, data: dict, headers: dict):
        with open(file_path, "rb") as audio_file:
            return requests.post(
                self.api_url,
                files={"file": audio_file},
                data=data,
                headers=headers,
                timeout=(3, self.timeout_seconds),
            )

    async def speech_to_text(self, opus_data: List[bytes], session_id: str, artifacts=None) -> Tuple[Optional[str], Optional[str]]:
        file_path = None
        try:
            if artifacts is None:
                return "", None
            file_path = artifacts.file_path
                
            logger.bind(tag=TAG).info(f"file path: {file_path}")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }
            
            # 使用data参数传递模型名称
            data = {
                "model": self.model
            }
            if self.language:
                data["language"] = self.language
            if self.prompt:
                data["prompt"] = self.prompt
            if self.hotwords:
                data["hotwords"] = self.hotwords


            start_time = time.time()
            response = await asyncio.to_thread(
                self._post_audio, file_path, data, headers
            )
            logger.bind(tag=TAG).debug(
                f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {response.text}"
            )

            if response.status_code == 200:
                text = self._sanitize_transcript(response.json().get("text", ""))
                return text, file_path
            else:
                raise Exception(f"API请求失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}")
            return "", None
        
