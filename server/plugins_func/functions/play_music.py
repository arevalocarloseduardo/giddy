import asyncio
import difflib
import json
import os
import random
import re
import threading
import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from core.utils.media_tools import configure_media_tools
from core.utils.music_queries import fold_music_query, normalize_music_query
from plugins_func.register import Action, ActionResponse, ToolType, register_function

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


TAG = __name__
SERVER_DIR = Path(__file__).resolve().parents[2]
MUSIC_CACHE = {}
YOUTUBE_DOWNLOAD_LOCK = threading.Lock()


class MusicPlaybackError(RuntimeError):
    pass


play_music_function_desc = {
    "type": "function",
    "function": {
        "name": "play_music",
        "description": (
            "Reproduce una cancion o musica pedida por el usuario. Busca primero en la "
            "biblioteca local y luego en YouTube. Tambien acepta una URL de YouTube."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "song_name": {
                    "type": "string",
                    "description": (
                        "Nombre de la cancion, artista o URL de YouTube. Usa 'random' si "
                        "el usuario no especifico una cancion."
                    ),
                }
            },
            "required": ["song_name"],
        },
    },
}


@register_function("play_music", play_music_function_desc, ToolType.SYSTEM_CTL)
async def play_music(conn: "ConnectionHandler", song_name: str):
    try:
        title = await handle_music_request(conn, song_name)
        conn.giddy_pending_music_until = 0.0
        return ActionResponse(
            action=Action.RECORD,
            result=f"Reproduciendo {title}",
            response=None,
        )
    except Exception as exc:
        conn.giddy_pending_music_until = time.monotonic() + 75.0
        conn.logger.bind(tag=TAG).error(f"No se pudo reproducir musica: {exc}")
        conn.logger.bind(tag=TAG).debug(traceback.format_exc())
        return ActionResponse(
            action=Action.RECORD,
            result=str(exc),
            response=None,
        )


def _resolve_config_path(raw_path: str, default: Path) -> Path:
    path = Path(raw_path).expanduser() if raw_path else default
    if not path.is_absolute():
        path = SERVER_DIR / path
    return path.resolve()


def initialize_music_handler(conn: "ConnectionHandler"):
    global MUSIC_CACHE
    if MUSIC_CACHE:
        return MUSIC_CACHE

    config = conn.config.get("plugins", {}).get("play_music", {})
    music_dir = _resolve_config_path(config.get("music_dir", "music"), SERVER_DIR / "music")
    youtube_cache_dir = _resolve_config_path(
        config.get("youtube_cache_dir", "data/giddy-youtube-cache"),
        SERVER_DIR / "data" / "giddy-youtube-cache",
    )
    extensions = tuple(
        str(ext).lower() for ext in config.get("music_ext", (".mp3", ".wav", ".p3"))
    )
    youtube_aliases = {}
    youtube_alias_titles = {}
    for alias, raw_target in config.get("youtube_aliases", {}).items():
        if isinstance(raw_target, dict):
            target = str(raw_target.get("url") or raw_target.get("source") or "").strip()
            title = str(raw_target.get("title") or alias).strip()
        else:
            target = str(raw_target).strip()
            title = str(alias).strip()
        if not str(alias).strip() or not target:
            continue
        youtube_aliases[fold_music_query(alias)] = target
        youtube_alias_titles.setdefault(target.casefold(), title)

    youtube_queries = _load_youtube_query_cache(youtube_cache_dir)
    for target_key, title in youtube_alias_titles.items():
        video_id = _youtube_video_id(target_key)
        audio_path = youtube_cache_dir / f"{video_id}.mp3" if video_id else None
        if audio_path and audio_path.is_file():
            youtube_queries.setdefault(
                target_key,
                {"path": str(audio_path), "title": title},
            )

    MUSIC_CACHE = {
        "music_config": config,
        "music_dir": str(music_dir),
        "music_ext": extensions,
        "refresh_time": max(10, int(config.get("refresh_time", 300))),
        "youtube_enabled": bool(config.get("youtube_enabled", True)),
        "youtube_cache_dir": str(youtube_cache_dir),
        "youtube_max_duration": max(60, int(config.get("youtube_max_duration", 900))),
        "youtube_timeout": max(15, int(config.get("youtube_timeout", 60))),
        "youtube_cache_files": max(1, int(config.get("youtube_cache_files", 10))),
        "youtube_cache_mb": max(32, int(config.get("youtube_cache_mb", 384))),
        "youtube_max_file_mb": max(8, int(config.get("youtube_max_file_mb", 64))),
        "youtube_default_query": str(
            config.get("youtube_default_query", "musica para escuchar")
        ).strip(),
        "youtube_aliases": youtube_aliases,
        "youtube_alias_titles": youtube_alias_titles,
        "youtube_queries": youtube_queries,
    }
    MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = get_music_files(
        music_dir, extensions
    )
    MUSIC_CACHE["scan_time"] = time.time()
    return MUSIC_CACHE


def get_music_files(music_dir, music_ext):
    directory = Path(music_dir)
    if not directory.is_dir():
        return [], []

    music_files = []
    music_file_names = []
    for file in directory.rglob("*"):
        if file.is_file() and file.suffix.lower() in music_ext:
            relative = str(file.relative_to(directory))
            music_files.append(relative)
            music_file_names.append(os.path.splitext(relative)[0])
    return music_files, music_file_names


def _refresh_local_music():
    if time.time() - MUSIC_CACHE["scan_time"] <= MUSIC_CACHE["refresh_time"]:
        return
    MUSIC_CACHE["music_files"], MUSIC_CACHE["music_file_names"] = get_music_files(
        MUSIC_CACHE["music_dir"], MUSIC_CACHE["music_ext"]
    )
    MUSIC_CACHE["scan_time"] = time.time()


def _extract_song_name(text):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return "random"

    command = re.compile(
        r"^¿?(?:pon(?:e|é|eme|éme)?|reproduc(?:i|í|e|ir)|toc(?:a|á)(?:me)?|"
        r"escuch(?:a|á|amos)|quiero\s+(?:escuchar|oir|oír)|"
        r"(?:me\s+)?(?:pod(?:e|é)s|puede|podr[ií]a(?:s)?)\s+"
        r"(?:poner|reproducir|tocar)|quiero\s+que\s+(?:pongas|reproduzcas|toques))\s+"
        r"(?:(?:(?:en|de|desde)\s+)?(?:youtube|yutub|yotube)\s+|"
        r"(?:(?:(?:la|una)\s+)?canci[oó]n|(?:el|un)\s+tema|m[uú]sica)\s+){0,2}",
        re.IGNORECASE,
    )
    cleaned = command.sub("", value, count=1).strip(" .,:;!?")
    return normalize_music_query(cleaned)


def _find_best_match(potential_song, music_files):
    query = os.path.splitext(str(potential_song))[0].casefold()
    best_match = None
    highest_ratio = 0.0
    for music_file in music_files:
        song_name = os.path.splitext(music_file)[0].casefold()
        ratio = difflib.SequenceMatcher(None, query, song_name).ratio()
        if ratio > highest_ratio and ratio >= 0.45:
            highest_ratio = ratio
            best_match = music_file
    return best_match


def _is_youtube_url(value: str) -> bool:
    return bool(
        re.match(
            r"^https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/",
            value,
            flags=re.IGNORECASE,
        )
    )


def _youtube_video_id(value: str):
    if not _is_youtube_url(value):
        return None
    parsed = urlparse(value)
    host = parsed.netloc.casefold().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
    else:
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        if not candidate and parsed.path.startswith("/shorts/"):
            candidate = parsed.path.split("/", 3)[2]
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", candidate or "") else None


def _youtube_source(query: str) -> str:
    return query if _is_youtube_url(query) else f"ytsearch1:{query}"


def _resolve_youtube_query(query: str) -> str:
    if _is_youtube_url(query):
        return query

    key = fold_music_query(query)
    aliases = MUSIC_CACHE.get("youtube_aliases", {})
    if key in aliases:
        return aliases[key]
    for alias in sorted(aliases, key=len, reverse=True):
        if len(alias.split()) >= 3 and alias in key:
            return aliases[alias]
    return f"{query} audio oficial"


def _youtube_match_filter(max_duration: int):
    def match(info, *, incomplete=False):
        if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
            return "No se reproducen transmisiones en vivo"
        duration = info.get("duration")
        if duration and float(duration) > max_duration:
            return f"El audio supera el limite de {max_duration // 60} minutos"
        return None

    return match


def _cached_youtube_result(query: str):
    cached = MUSIC_CACHE.get("youtube_queries", {}).get(query.casefold())
    if not cached:
        return None
    path = Path(cached["path"])
    return (path, cached["title"]) if path.is_file() else None


def _load_youtube_query_cache(cache_dir: Path):
    index_path = cache_dir / "index.json"
    if not index_path.is_file():
        return {}
    try:
        raw_entries = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    entries = {}
    for query, item in raw_entries.items() if isinstance(raw_entries, dict) else ():
        if not isinstance(item, dict):
            continue
        filename = Path(str(item.get("file") or "")).name
        audio_path = cache_dir / filename
        title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()[:120]
        if filename.endswith(".mp3") and audio_path.is_file() and title:
            entries[str(query).casefold()] = {"path": str(audio_path), "title": title}
    return entries


def _remember_youtube_result(query: str, audio_path: Path, title: str):
    MUSIC_CACHE["youtube_queries"][query.casefold()] = {
        "path": str(audio_path),
        "title": title,
    }
    index = {
        key: {"file": Path(item["path"]).name, "title": item["title"]}
        for key, item in MUSIC_CACHE["youtube_queries"].items()
        if Path(item["path"]).is_file()
    }
    index_path = Path(MUSIC_CACHE["youtube_cache_dir"]) / "index.json"
    temporary_path = index_path.with_suffix(".json.tmp")
    try:
        temporary_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(index_path)
    except OSError:
        temporary_path.unlink(missing_ok=True)


def _prune_youtube_cache(cache_dir: Path, protected: Path):
    files = sorted(
        (path for path in cache_dir.glob("*.mp3") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    max_files = MUSIC_CACHE["youtube_cache_files"]
    max_bytes = MUSIC_CACHE["youtube_cache_mb"] * 1024 * 1024
    retained_bytes = 0
    for index, path in enumerate(files):
        retained_bytes += path.stat().st_size
        if path == protected:
            continue
        if index >= max_files or retained_bytes > max_bytes:
            path.unlink(missing_ok=True)


def _download_youtube_audio(query: str):
    cached = _cached_youtube_result(query)
    if cached:
        return cached

    try:
        import yt_dlp
    except ImportError as exc:
        raise MusicPlaybackError("yt-dlp no esta instalado en el servidor") from exc

    cache_dir = Path(MUSIC_CACHE["youtube_cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = configure_media_tools()

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(cache_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "socket_timeout": 12,
        "retries": 2,
        "fragment_retries": 2,
        "extractor_retries": 2,
        "max_filesize": MUSIC_CACHE["youtube_max_file_mb"] * 1024 * 1024,
        "overwrites": True,
        "match_filter": _youtube_match_filter(MUSIC_CACHE["youtube_max_duration"]),
        "ffmpeg_location": ffmpeg,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "160",
            }
        ],
    }

    with YOUTUBE_DOWNLOAD_LOCK:
        cached = _cached_youtube_result(query)
        if cached:
            return cached
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(_youtube_source(query), download=True)
        except Exception as exc:
            raise MusicPlaybackError("YouTube no devolvio un audio reproducible") from exc

        if info and info.get("entries"):
            info = next((entry for entry in info["entries"] if entry), None)
        if not info or not info.get("id"):
            raise MusicPlaybackError("No encontre esa cancion en YouTube")

        expected_paths = [cache_dir / f"{info['id']}.mp3"]
        prepared_path = Path(downloader.prepare_filename(info))
        expected_paths.append(prepared_path.with_suffix(".mp3"))
        for requested in info.get("requested_downloads") or ():
            requested_path = Path(str(requested.get("filepath") or ""))
            if requested_path.name:
                expected_paths.append(requested_path.with_suffix(".mp3"))
        audio_path = next((path for path in expected_paths if path.is_file()), None)
        if audio_path is None:
            raise MusicPlaybackError("No pude preparar el audio encontrado")

        title = re.sub(r"\s+", " ", str(info.get("title") or query)).strip()[:120]
        _remember_youtube_result(query, audio_path, title)
        _prune_youtube_cache(cache_dir, audio_path)
        return audio_path, title


def _queue_message(conn, sentence_type, content_type, *, text=None, file_path=None):
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=sentence_type,
            content_type=content_type,
            content_detail=text,
            content_file=str(file_path) if file_path else None,
        )
    )


async def _open_music_stream(conn):
    conn.tts_emotion = {
        "sentence_id": conn.sentence_id,
        "emotion": "music",
    }
    await conn.websocket.send(
        json.dumps(
            {
                "type": "llm",
                "emotion": "music",
                "session_id": conn.session_id,
            }
        )
    )
    _queue_message(conn, SentenceType.FIRST, ContentType.ACTION)


def _close_music_stream(conn):
    _queue_message(conn, SentenceType.LAST, ContentType.ACTION)


def _queue_spoken_text(conn, text: str):
    conn.tts.store_tts_text(conn.sentence_id, text)
    _queue_message(conn, SentenceType.MIDDLE, ContentType.TEXT, text=text)


def _queue_audio_file(conn, path: Path):
    _queue_message(conn, SentenceType.MIDDLE, ContentType.FILE, file_path=path)


def _announcement(title: str) -> str:
    return f"Pongo {title}."


async def handle_music_request(conn: "ConnectionHandler", song_name: str):
    initialize_music_handler(conn)
    _refresh_local_music()
    query = _extract_song_name(song_name)

    if query == "random" and MUSIC_CACHE["music_files"]:
        selected = random.choice(MUSIC_CACHE["music_files"])
        path = Path(MUSIC_CACHE["music_dir"]) / selected
        title = Path(selected).stem
        await _open_music_stream(conn)
        _queue_spoken_text(conn, _announcement(title))
        _queue_audio_file(conn, path)
        _close_music_stream(conn)
        return title

    if query != "random":
        local_match = _find_best_match(query, MUSIC_CACHE["music_files"])
        if local_match:
            path = Path(MUSIC_CACHE["music_dir"]) / local_match
            title = Path(local_match).stem
            await _open_music_stream(conn)
            _queue_spoken_text(conn, _announcement(title))
            _queue_audio_file(conn, path)
            _close_music_stream(conn)
            return title

    if not MUSIC_CACHE["youtube_enabled"]:
        raise MusicPlaybackError("La reproduccion desde YouTube esta desactivada")

    youtube_query = query if query != "random" else MUSIC_CACHE["youtube_default_query"]
    youtube_query = _resolve_youtube_query(youtube_query)
    await _open_music_stream(conn)
    try:
        cached = _cached_youtube_result(youtube_query)
        if cached:
            path, title = cached
        else:
            _queue_spoken_text(conn, "Dame un momento, busco la musica.")
            path, title = await asyncio.wait_for(
                asyncio.to_thread(_download_youtube_audio, youtube_query),
                timeout=MUSIC_CACHE["youtube_timeout"],
            )
        _queue_spoken_text(conn, _announcement(title))
        _queue_audio_file(conn, path)
        _close_music_stream(conn)
        return title
    except Exception as exc:
        _queue_spoken_text(conn, "No pude traer esa cancion. Proba diciendome el artista tambien.")
        _close_music_stream(conn)
        if isinstance(exc, MusicPlaybackError):
            raise
        if isinstance(exc, asyncio.TimeoutError):
            raise MusicPlaybackError("YouTube demoro demasiado") from exc
        raise MusicPlaybackError("Fallo la busqueda de musica") from exc


async def handle_music_command(conn: "ConnectionHandler", text):
    await handle_music_request(conn, text)
    return True


async def play_local_music(conn: "ConnectionHandler", specific_file=None):
    initialize_music_handler(conn)
    selected = specific_file
    if selected is None and MUSIC_CACHE["music_files"]:
        selected = random.choice(MUSIC_CACHE["music_files"])
    if not selected:
        raise MusicPlaybackError("No hay musica local disponible")

    path = Path(MUSIC_CACHE["music_dir"]) / selected
    if not path.is_file():
        raise MusicPlaybackError("El archivo de musica ya no existe")
    title = Path(selected).stem
    await _open_music_stream(conn)
    _queue_spoken_text(conn, _announcement(title))
    _queue_audio_file(conn, path)
    _close_music_stream(conn)
