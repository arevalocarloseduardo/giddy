import asyncio
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from faster_whisper import WhisperModel


MODEL_NAME = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

app = FastAPI(title="Hermes Local STT")
_model = None


def model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)
    return _model


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", normalized).strip().lower()


def sanitize_transcript(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    normalized = _normalize(text)
    hallucinations = (
        "subtitulos realizados por la comunidad de amara.org",
        "subtitulos por la comunidad de amara.org",
        "gracias por ver el video",
    )
    if any(phrase in normalized for phrase in hallucinations):
        return ""

    words = re.findall(r"[a-z0-9]+", normalized)
    if len(words) >= 6:
        most_repeated = max(
            (words.count(word) for word in set(words)), default=0
        )
        if most_repeated >= 4 and most_repeated / len(words) >= 0.45:
            return ""
    return text


def _transcribe_file(
    path: str,
    language: str | None,
    prompt: str | None = None,
    hotwords: str | None = None,
):
    segments, info = model().transcribe(
        path,
        language=(language or None),
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 320,
        },
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        initial_prompt=(prompt or None),
        hotwords=(hotwords or None),
        no_speech_threshold=0.65,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    text = " ".join((segment.text or "").strip() for segment in segments).strip()
    return sanitize_transcript(text), info


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "loaded": _model is not None,
    }


@app.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [{"id": "whisper-1", "object": "model", "owned_by": "local"}],
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    hotwords: str | None = Form(default=None),
):
    suffix = Path(file.filename or "audio.ogg").suffix or ".ogg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        path = tmp.name

    try:
        text, info = await asyncio.to_thread(
            _transcribe_file, path, language, prompt, hotwords
        )
        return {
            "success": True,
            "text": text,
            "language": getattr(info, "language", None),
            "duration": getattr(info, "duration", None),
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@app.post("/v1/audio/transcriptions")
async def openai_transcribe(
    file: UploadFile = File(...),
    model_name: str | None = Form(default=None, alias="model"),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    hotwords: str | None = Form(default=None),
):
    result = await transcribe(
        file=file,
        language=language,
        prompt=prompt,
        hotwords=hotwords,
    )
    return {"text": result["text"]}
