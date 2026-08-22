import re
import unicodedata


def fold_music_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def normalize_music_query(value: str) -> str:
    """Repair common Spanish ASR variants without involving a language model."""
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;!?¿¡")
    cleaned = re.sub(
        r"\bllamad[oa]\s+(?:de\s+)?emergencia(?:\s+baby)?\b",
        "Llamado de Emergencia",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:dadi|dady|daddy)\s+(?:yankee|yanqui|junkins?)\b",
        "Daddy Yankee",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:grupo\s+)?(?:nietzsche|nietche|niche)\b",
        "Grupo Niche",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bGrupo\s+Grupo\s+Niche\b", "Grupo Niche", cleaned)
    cleaned = re.sub(
        r"^de\s+(?=Grupo\s+Niche(?:\s|$))",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned or "random"
