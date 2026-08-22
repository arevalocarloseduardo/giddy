import json
import re
import unicodedata


CHAT_MODE = "chat"
LISTEN_ONLY_MODE = "listen_only"
SLEEP_MODE = "sleep"

_WAKE_WORD = re.compile(r"\bgiddy\b")
_WAKE_ONLY = re.compile(r"^(?:hey |hola )?giddy$")

_LISTEN_ONLY_PATTERNS = (
    re.compile(r"\bescucha(?:me)?\b.*\b(?:no (?:me )?hables|sin hablar)\b"),
    re.compile(r"\bsegui escuchando\b.*\b(?:no (?:me )?hables|sin hablar)\b"),
    re.compile(r"\b(?:no (?:me )?hables|sin hablar)\b.*\b(?:escucha(?:me)?|segui escuchando)\b"),
    re.compile(r"\b(?:modo silencioso|solo escucha|escucha en silencio)\b"),
    re.compile(r"\b(?:hace|hagas|ejecuta|segui haciendo)\b.*\b(?:sin hablar|sin voz)\b"),
)

_SLEEP_PATTERNS = (
    re.compile(r"\b(?:callate|dormite|andate a dormir|anda a dormir|ponete a dormir)\b"),
    re.compile(r"\b(?:no me escuches|deja de escucharme|deja de escuchar|no escuches mas)\b"),
    re.compile(r"^(?:silencio|a dormir|basta por hoy)$"),
    re.compile(r"^(?:chau|adios|hasta luego|nos vemos|hasta manana|buenas noches)(?: giddy)?$"),
)

_RESTORE_VOICE_PATTERNS = (
    re.compile(r"\b(?:volve a hablar|volvi a hablar|ya podes hablar|hablame de nuevo)\b"),
)


def normalize_interaction_text(text):
    decomposed = unicodedata.normalize("NFKD", str(text or "").casefold())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return re.sub(
        r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", without_accents)
    ).strip()


def detect_interaction_mode(text, current_mode=CHAT_MODE):
    normalized = normalize_interaction_text(text)
    if not normalized:
        return None

    if current_mode == LISTEN_ONLY_MODE and (
        _WAKE_WORD.search(normalized)
        or any(pattern.search(normalized) for pattern in _RESTORE_VOICE_PATTERNS)
    ):
        return CHAT_MODE

    if any(pattern.search(normalized) for pattern in _LISTEN_ONLY_PATTERNS):
        return LISTEN_ONLY_MODE

    if normalized == "no me hables":
        return LISTEN_ONLY_MODE

    if any(pattern.search(normalized) for pattern in _SLEEP_PATTERNS):
        return SLEEP_MODE

    return None


def is_wake_only_command(text):
    return bool(_WAKE_ONLY.fullmatch(normalize_interaction_text(text)))


def voice_output_enabled(conn):
    return getattr(conn, "giddy_interaction_mode", CHAT_MODE) != LISTEN_ONLY_MODE


async def send_interaction_mode(conn, mode):
    websocket = getattr(conn, "websocket", None)
    if websocket is None:
        return False

    message = {
        "type": "system",
        "command": "set_interaction_mode",
        "mode": mode,
        "session_id": getattr(conn, "session_id", None),
    }
    try:
        await websocket.send(json.dumps(message))
        return True
    except Exception as exc:
        logger = getattr(conn, "logger", None)
        if logger is not None:
            logger.bind(tag=__name__).warning(
                f"No se pudo enviar el modo de interaccion {mode}: {exc}"
            )
        return False
