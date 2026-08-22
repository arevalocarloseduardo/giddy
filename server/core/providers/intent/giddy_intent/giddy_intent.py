import json
import re
import time
from typing import Dict, List

from ..base import IntentProviderBase
from core.utils.image_queries import (
    is_image_creation_request,
    parse_image_description,
    parse_image_request,
)
from core.utils.music_queries import fold_music_query, normalize_music_query


MUSIC_ACTION = re.compile(
    r"\b(?:pone(?:me)?|ponga(?:s)?|"
    r"reproduc(?:i(?:me|la|lo)?|e(?:me|la|lo)?|ir)|"
    r"reproduzc(?:a|as|o)|toca(?:me|la|lo)?|toque(?:s)?|"
    r"escuch(?:a(?:me|la|lo)?|ar)|oir)\b",
    re.IGNORECASE,
)
NAMED_MUSIC_COMMAND = re.compile(
    r"\b(?:busca|encontra)\b.*?\b(?:cancion|tema)\b\s+"
    r"(?:que\s+se\s+llama\s+|llamad[oa]\s+)?"
    r"(?P<song>.+?)"
    r"(?=\s+(?:y\s+)?(?:reproduci(?:la)?|reproduce|reproducir|"
    r"pone(?:la)?|toca(?:la)?|escucha(?:la)?)\b)",
    re.IGNORECASE,
)
MEDIA_ONLY = re.compile(
    r"^(?:(?:la|una?|el)\s+)?(?:cancion|tema|musica)\s*$",
    re.IGNORECASE,
)
SPOKEN_MUSIC_TITLE = re.compile(
    r"^(?:(?:un|una|si|eh|giddy)\s+){0,3}"
    r"(?:(?:la|el|un|una)\s+)?(?:cancion|tema)\s+"
    r"(?:de|llamad[oa])\s+(?P<song>.+)$",
    re.IGNORECASE,
)
WEATHER_WORD = re.compile(
    r"\b(?:clima|pronostico|tiempo|temperatura|grados?|lluvia|llover)\b",
    re.IGNORECASE,
)
AMBIGUOUS_WEATHER_WORD = re.compile(
    r"\b(?:frio|calor|helado)\b",
    re.IGNORECASE,
)
WEATHER_CUE = re.compile(
    r"(?:^|\b)(?:que|como|cuanto|cuanta|cuantos|cuantas|decime|dime|dame|"
    r"mostrame|hoy|manana|"
    r"ahora|hace|esta|habra|va\s+a)\b",
    re.IGNORECASE,
)
WEATHER_TIME_CUE = re.compile(
    r"\b(?:hoy|manana|ahora|esta\s+noche|va\s+a|hace|hara|habra)\b",
    re.IGNORECASE,
)
WEATHER_LOCATION = re.compile(
    r"\b(?:en|para)\s+(?P<location>.+?)(?:\s+(?:hoy|manana|ahora))?[.!?]*$",
    re.IGNORECASE,
)
PENDING_IMAGE_SECONDS = 60.0
PENDING_MUSIC_SECONDS = 75.0
PENDING_IMAGE_CANCEL = re.compile(
    r"^\s*(?:no|cancela|cancelar|dejalo|olvidalo|mejor\s+no)\b",
    re.IGNORECASE,
)
UNRELATED_QUESTION = re.compile(
    r"^\s*(?:que|cual|como|cuando|donde|por\s+que|quien)\b",
    re.IGNORECASE,
)


def _function_call(name, arguments=None):
    payload = {"name": name}
    if arguments is not None:
        payload["arguments"] = arguments
    return json.dumps({"function_call": payload}, ensure_ascii=False)


def _extract_music_request(value: str):
    folded = fold_music_query(value)
    spoken_title = SPOKEN_MUSIC_TITLE.search(folded)
    if spoken_title:
        return spoken_title.group("song").strip(" .,:;!?\u00bf\u00a1")

    named = NAMED_MUSIC_COMMAND.search(folded)
    if named:
        start, end = named.span("song")
        return value[start:end].strip(" .,:;!?\u00bf\u00a1")

    action = MUSIC_ACTION.search(folded)
    if not action:
        return None

    tail = value[action.end() :].strip(" .,:;!?\u00bf\u00a1")
    original_tail = tail
    prefixes = (
        r"^(?:por\s+favor\s+)",
        r"^a\s+(?:una?\s+)?(?:cancion|tema)\s+que\s+sea\s+"
        r"(?:una?\s+)?de\s+",
        r"^(?:(?:la|una?|el)\s+)?(?:cancion|tema|musica)\s+"
        r"(?:(?:de|en|desde)\s+)?(?:youtube|yutub|yotube)\s+",
        r"^(?:(?:en|de|desde)\s+)?(?:youtube|yutub|yotube)\s+",
        r"^(?:(?:la|una?|el)\s+)?(?:cancion|tema|musica)\s+",
    )
    for prefix in prefixes:
        match = re.match(prefix, fold_music_query(tail))
        if match:
            tail = tail[match.end() :]
    tail = tail.strip(" .,:;!?\u00bf\u00a1")
    if tail:
        return tail
    if MEDIA_ONLY.match(fold_music_query(original_tail)):
        return "random"
    return None


def _pending_image_description(conn, value):
    if conn is None:
        return None
    pending_until = float(getattr(conn, "giddy_pending_image_until", 0.0) or 0.0)
    if pending_until <= 0:
        return None
    conn.giddy_pending_image_until = 0.0
    if time.monotonic() > pending_until:
        return None

    folded = fold_music_query(value)
    if PENDING_IMAGE_CANCEL.match(folded):
        return None
    if UNRELATED_QUESTION.match(folded) and not folded.startswith("que muestre"):
        return None
    return parse_image_description(value)


def _known_music_alias(conn, value):
    if conn is None:
        return None
    aliases = (
        getattr(conn, "config", {})
        .get("plugins", {})
        .get("play_music", {})
        .get("youtube_aliases", {})
    )
    folded = fold_music_query(value)
    if folded in {fold_music_query(alias) for alias in aliases}:
        return normalize_music_query(value)
    return None


def _pending_music_request(conn, value):
    if conn is None:
        return None
    pending_until = float(getattr(conn, "giddy_pending_music_until", 0.0) or 0.0)
    if pending_until <= 0 or time.monotonic() > pending_until:
        return None

    folded = fold_music_query(value)
    if PENDING_IMAGE_CANCEL.match(folded) or UNRELATED_QUESTION.match(folded):
        conn.giddy_pending_music_until = 0.0
        return None
    if MUSIC_ACTION.search(folded):
        return None
    if len(folded.split()) < 2:
        return None
    conn.giddy_pending_music_until = 0.0
    return normalize_music_query(value)


class IntentProvider(IntentProviderBase):
    async def detect_intent(
        self, conn, dialogue_history: List[Dict], text: str
    ) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()

        image_request = parse_image_request(value)
        if image_request:
            if conn is not None:
                conn.giddy_pending_image_until = 0.0
            prompt, aspect_ratio = image_request
            return _function_call(
                "generate_image",
                {"prompt": prompt, "aspect_ratio": aspect_ratio},
            )

        if is_image_creation_request(value):
            if conn is not None:
                conn.giddy_pending_image_until = time.monotonic() + PENDING_IMAGE_SECONDS
            return _function_call(
                "generate_image",
                {"prompt": "", "aspect_ratio": "square"},
            )

        folded = fold_music_query(value)
        is_weather_request = (
            WEATHER_WORD.search(folded)
            and (WEATHER_CUE.search(folded) or len(folded.split()) <= 5)
        ) or (
            AMBIGUOUS_WEATHER_WORD.search(folded)
            and WEATHER_TIME_CUE.search(folded)
        )
        if is_weather_request:
            location_match = WEATHER_LOCATION.search(folded)
            location = (
                value[
                    location_match.start("location") : location_match.end("location")
                ].strip(" .,:;!?\u00bf\u00a1")
                if location_match
                else ""
            )
            day = "tomorrow" if re.search(r"\bmanana\b", folded) else "today"
            return _function_call(
                "get_giddy_weather",
                {"location": location, "day": day},
            )

        song = _extract_music_request(value)
        if not song:
            song = _known_music_alias(conn, value) or _pending_music_request(conn, value)
        if song:
            if conn is not None:
                conn.giddy_pending_image_until = 0.0
            return _function_call(
                "play_music",
                {"song_name": normalize_music_query(song)},
            )

        if conn is not None and MUSIC_ACTION.search(folded):
            conn.giddy_pending_music_until = time.monotonic() + PENDING_MUSIC_SECONDS

        pending_image = _pending_image_description(conn, value)
        if pending_image:
            prompt, aspect_ratio = pending_image
            return _function_call(
                "generate_image",
                {"prompt": prompt, "aspect_ratio": aspect_ratio},
            )

        return _function_call("continue_chat")
