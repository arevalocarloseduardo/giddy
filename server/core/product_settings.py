import copy
import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_QUICK_ACTIONS = [
    {
        "id": "agenda",
        "label": "Mi agenda",
        "prompt": "Dame un resumen breve de mi agenda de hoy y avisame si hay conflictos.",
    },
    {
        "id": "priorities",
        "label": "Prioridades",
        "prompt": "Decime mis tres prioridades mas importantes para hoy usando lo que sabes de mi.",
    },
    {
        "id": "focus",
        "label": "Foco 25 min",
        "prompt": "Inicia una sesion de foco de 25 minutos y avisame cuando termine.",
    },
    {
        "id": "weather",
        "label": "Clima",
        "prompt": "Decime el clima de hoy en mi ubicacion y si necesito llevar abrigo o paraguas.",
    },
]

DEFAULT_INSTANT_RESPONSES = [
    {
        "id": "wellbeing",
        "triggers": [
            "como estas",
            "como andas",
            "todo bien",
            "hola como estas",
            "hola como andas",
            "hola giddy como estas",
        ],
        "response": "Muy bien. ¿Vos?",
    },
    {
        "id": "greeting",
        "triggers": [
            "hola",
            "buenas",
            "hola giddy",
            "buen dia",
            "buenas tardes",
            "buenas noches",
        ],
        "response": "Hola. ¿Cómo estás?",
    },
    {
        "id": "presence",
        "triggers": ["estas ahi", "me escuchas", "giddy estas ahi"],
        "response": "Sí. Te escucho.",
    },
    {
        "id": "thanks",
        "triggers": ["gracias", "muchas gracias", "gracias giddy"],
        "response": "De nada.",
    },
    {
        "id": "farewell",
        "triggers": ["chau", "adios", "hasta luego", "nos vemos"],
        "response": "Nos vemos.",
    },
    {
        "id": "identity",
        "triggers": ["quien sos", "como te llamas"],
        "response": "Soy Giddy. ¿En qué te ayudo?",
    },
    {
        "id": "capabilities",
        "triggers": ["que podes hacer", "en que me podes ayudar"],
        "response": "Puedo conversar, organizarte y usar tus herramientas. ¿Qué necesitás?",
    },
]

VOICE_NUMBER_WORDS = {
    "cero", "una", "uno", "dos", "tres", "cuatro", "cinco", "seis",
    "siete", "ocho", "nueve", "diez", "once", "doce", "trece",
    "catorce", "quince", "dieciséis", "diecisiete", "dieciocho",
    "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
    "veinticuatro", "veinticinco", "veintiséis", "veintisiete",
    "veintiocho", "veintinueve", "treinta", "cuarenta", "cincuenta",
}
VOICE_TIME_WORDS = VOICE_NUMBER_WORDS | {
    "son", "las", "es", "la", "en", "punto", "y", "cuarto", "media",
}
VOICE_DATE_WORDS = VOICE_NUMBER_WORDS | {
    "hoy", "es", "de", "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo", "enero", "febrero", "marzo", "abril",
    "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
    "noviembre", "diciembre",
}


ALLOWED_VOICES = {
    "es-AR-ElenaNeural",
    "es-AR-TomasNeural",
    "es-MX-DaliaNeural",
    "es-UY-ValentinaNeural",
}

VOICE_PROFILES = {
    "robot": {
        "voice": "es-AR-TomasNeural",
        "rate": 5,
        "pitch": 8,
    },
    "young": {
        "voice": "es-AR-TomasNeural",
        "rate": 10,
        "pitch": 28,
    },
    "natural": {
        "voice": "es-AR-ElenaNeural",
        "rate": 6,
        "pitch": 0,
    },
}
ALLOWED_VOICE_PROFILES = set(VOICE_PROFILES)


DEFAULT_SETTINGS = {
    "schema_version": 4,
    "assistant_name": "Giddy",
    "mode": "balanced",
    "voice": {
        "profile": "robot",
        **VOICE_PROFILES["robot"],
    },
    "routing": {
        "local_model": "qwen3.5:9b",
        "local_url": "http://127.0.0.1:11434",
        "local_context_chars": 2600,
        "power_context_chars": 6000,
        "local_max_tokens": 96,
        "power_max_tokens": 480,
        "local_timeout_seconds": 5,
        "keep_alive": "2h",
    },
    "experience": {
        "instant_enabled": True,
        "thinking_cue_enabled": True,
        "voice_cache_enabled": True,
        "time_zone": "America/Argentina/Buenos_Aires",
        "local_cue": "",
        "thinking_cue": "Dame un segundo.",
        "instant_responses": DEFAULT_INSTANT_RESPONSES,
    },
    "quick_actions": DEFAULT_QUICK_ACTIONS,
}


class ProductSettings:
    def __init__(self, path=None):
        server_dir = Path(__file__).resolve().parents[1]
        self.path = Path(path) if path else server_dir / "data" / "giddy-product.json"
        if not self.path.is_absolute():
            self.path = server_dir / self.path
        self.token_path = self.path.parent / "giddy-setup-token.txt"
        self.metrics_path = self.path.parent / "giddy-routing.jsonl"
        self.voice_metrics_path = self.path.parent / "giddy-voice.jsonl"
        self._lock = threading.RLock()
        self._cached_mtime = None
        self._cached = None

    @staticmethod
    def _merge(base, override):
        result = copy.deepcopy(base)
        if not isinstance(override, dict):
            return result
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ProductSettings._merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def load(self):
        with self._lock:
            try:
                mtime = self.path.stat().st_mtime_ns
            except FileNotFoundError:
                mtime = None
            if self._cached is not None and self._cached_mtime == mtime:
                return copy.deepcopy(self._cached)

            raw = {}
            if mtime is not None:
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    raw = {}
            settings = self._validate(self._merge(DEFAULT_SETTINGS, raw))
            self._cached = settings
            self._cached_mtime = mtime
            return copy.deepcopy(settings)

    def save(self, incoming):
        with self._lock:
            current = self.load()
            merged = self._merge(current, incoming)
            validated = self._validate(merged)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_path, self.path)
            self._cached = validated
            self._cached_mtime = self.path.stat().st_mtime_ns
            return copy.deepcopy(validated)

    def setup_token(self):
        with self._lock:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            if self.token_path.exists():
                token = self.token_path.read_text(encoding="utf-8").strip()
                if len(token) >= 24:
                    return token
            token = secrets.token_urlsafe(32)
            self.token_path.write_text(token + "\n", encoding="utf-8")
            return token

    def append_route_metric(self, event):
        safe_event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "route": str(event.get("route", "unknown"))[:16],
            "reason": str(event.get("reason", "unknown"))[:80],
            "latency_ms": max(0, int(event.get("latency_ms", 0))),
            "input_chars": max(0, int(event.get("input_chars", 0))),
            "output_chars": max(0, int(event.get("output_chars", 0))),
            "prompt_tokens": max(0, int(event.get("prompt_tokens", 0))),
            "output_tokens": max(0, int(event.get("output_tokens", 0))),
            "fallback": bool(event.get("fallback", False)),
            "cue": bool(event.get("cue", False)),
        }
        session_id = str(event.get("session_id", ""))
        if session_id:
            safe_event["session"] = hashlib.sha256(session_id.encode()).hexdigest()[:12]
        with self._lock:
            self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
            if self.metrics_path.exists() and self.metrics_path.stat().st_size > 2_000_000:
                rotated = self.metrics_path.with_suffix(".previous.jsonl")
                os.replace(self.metrics_path, rotated)
            with self.metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(safe_event, ensure_ascii=False) + "\n")

    def append_voice_metric(self, cache_hit, latency_ms, text_chars):
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cache_hit": bool(cache_hit),
            "latency_ms": max(0, int(latency_ms)),
            "text_chars": max(0, int(text_chars)),
        }
        with self._lock:
            self.voice_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            if self.voice_metrics_path.exists() and self.voice_metrics_path.stat().st_size > 1_000_000:
                rotated = self.voice_metrics_path.with_suffix(".previous.jsonl")
                os.replace(self.voice_metrics_path, rotated)
            with self.voice_metrics_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def metrics_summary(self, hours=24):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        events = []
        if self.metrics_path.exists():
            try:
                lines = self.metrics_path.read_text(encoding="utf-8").splitlines()[-5000:]
                for line in lines:
                    try:
                        item = json.loads(line)
                        timestamp = datetime.fromisoformat(item["ts"])
                        if timestamp >= cutoff:
                            events.append(item)
                    except (KeyError, TypeError, ValueError):
                        continue
            except OSError:
                pass

        instant = [event for event in events if event.get("route") == "instant"]
        model_local = [event for event in events if event.get("route") == "local"]
        local = instant + model_local
        power = [event for event in events if event.get("route") == "power"]
        local_token_estimate = sum(
            event.get("prompt_tokens", 0) + event.get("output_tokens", 0)
            or (event.get("input_chars", 0) + event.get("output_chars", 0)) // 4
            for event in local
        )
        latencies = [event.get("latency_ms", 0) for event in events if event.get("latency_ms")]
        voice_events = []
        if self.voice_metrics_path.exists():
            try:
                for line in self.voice_metrics_path.read_text(encoding="utf-8").splitlines()[-5000:]:
                    try:
                        item = json.loads(line)
                        if datetime.fromisoformat(item["ts"]) >= cutoff:
                            voice_events.append(item)
                    except (KeyError, TypeError, ValueError):
                        continue
            except OSError:
                pass
        voice_hits = sum(1 for event in voice_events if event.get("cache_hit"))
        return {
            "hours": hours,
            "total": len(events),
            "local": len(local),
            "instant": len(instant),
            "model_local": len(model_local),
            "power": len(power),
            "local_share": round((len(local) / len(events) * 100), 1) if events else 0,
            "instant_share": round((len(instant) / len(events) * 100), 1) if events else 0,
            "estimated_api_tokens_saved": int(local_token_estimate),
            "average_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "fallbacks": sum(1 for event in events if event.get("fallback")),
            "voice_cache_hit_share": (
                round(voice_hits / len(voice_events) * 100, 1) if voice_events else 0
            ),
            "voice_requests": len(voice_events),
        }

    def resolve_quick_action(self, action_id):
        for action in self.load()["quick_actions"]:
            if action.get("id") == action_id:
                return copy.deepcopy(action)
        return None

    def voice_cache_phrases(self, settings=None):
        current = settings or self.load()
        experience = current.get("experience", {})
        phrases = [
            experience.get("local_cue", ""),
            experience.get("thinking_cue", ""),
        ]
        phrases.extend(
            item.get("response", "")
            for item in experience.get("instant_responses", [])
        )
        segments = set()
        for phrase in phrases:
            phrase_text = str(phrase).strip()
            if not phrase_text:
                continue
            segments.add(phrase_text)
            for segment in re.findall(r"[^,.;:!?]+[,.;:!?]*", phrase_text):
                raw = segment.strip()
                if raw:
                    segments.add(raw)
                clean = re.sub(r"^[¿¡\s]+|[,.;:!?¿¡\s]+$", "", raw).strip()
                if clean:
                    segments.add(clean)
        return sorted(segments)

    def is_cacheable_voice_text(self, text, settings=None):
        clean = str(text or "").strip()
        if not clean:
            return False
        current = settings or self.load()
        if not current.get("experience", {}).get("voice_cache_enabled", True):
            return False
        if clean in self.voice_cache_phrases(current):
            return True
        return self._is_safe_calendar_phrase(clean)

    @staticmethod
    def _is_safe_calendar_phrase(text):
        normalized = str(text).casefold().strip(" .,:;!?¿¡")
        if not re.fullmatch(r"[a-záéíóúñü ]+", normalized):
            return False
        tokens = re.findall(r"[a-záéíóúñü]+", normalized)
        if normalized.startswith(("son las ", "es la una")):
            return len(tokens) <= 10 and all(token in VOICE_TIME_WORDS for token in tokens)
        if normalized.startswith("hoy es "):
            return len(tokens) <= 8 and all(token in VOICE_DATE_WORDS for token in tokens)
        return False

    @staticmethod
    def _validate(settings):
        output = copy.deepcopy(DEFAULT_SETTINGS)
        source_schema = ProductSettings._bounded_int(
            settings.get("schema_version"), 1, 99, 1
        )
        output["assistant_name"] = str(settings.get("assistant_name", "Giddy")).strip()[:20] or "Giddy"

        mode = str(settings.get("mode", "balanced")).lower()
        output["mode"] = mode if mode in {"eco", "balanced", "max"} else "balanced"

        voice = settings.get("voice", {}) if isinstance(settings.get("voice"), dict) else {}
        requested_profile = str(voice.get("profile", "")).lower()
        if requested_profile in ALLOWED_VOICE_PROFILES:
            profile = requested_profile
        else:
            legacy_voice = str(voice.get("voice", ""))
            profile = (
                "natural"
                if legacy_voice in ALLOWED_VOICES and legacy_voice != "es-AR-TomasNeural"
                else "robot"
            )
        output["voice"]["profile"] = profile
        selected_voice = str(voice.get("voice", DEFAULT_SETTINGS["voice"]["voice"]))
        output["voice"]["voice"] = selected_voice if selected_voice in ALLOWED_VOICES else DEFAULT_SETTINGS["voice"]["voice"]
        output["voice"]["rate"] = ProductSettings._bounded_int(voice.get("rate"), -10, 40, DEFAULT_SETTINGS["voice"]["rate"])
        output["voice"]["pitch"] = ProductSettings._bounded_int(
            voice.get("pitch"), -50, 50, VOICE_PROFILES[profile]["pitch"]
        )

        routing = settings.get("routing", {}) if isinstance(settings.get("routing"), dict) else {}
        defaults = DEFAULT_SETTINGS["routing"]
        output["routing"] = {
            "local_model": str(routing.get("local_model", defaults["local_model"]))[:80],
            "local_url": str(routing.get("local_url", defaults["local_url"]))[:200],
            "local_context_chars": ProductSettings._bounded_int(routing.get("local_context_chars"), 800, 8000, defaults["local_context_chars"]),
            "power_context_chars": ProductSettings._bounded_int(routing.get("power_context_chars"), 2000, 16000, defaults["power_context_chars"]),
            "local_max_tokens": ProductSettings._bounded_int(routing.get("local_max_tokens"), 32, 180, defaults["local_max_tokens"]),
            "power_max_tokens": ProductSettings._bounded_int(routing.get("power_max_tokens"), 120, 1000, defaults["power_max_tokens"]),
            "local_timeout_seconds": ProductSettings._bounded_int(routing.get("local_timeout_seconds"), 3, 30, defaults["local_timeout_seconds"]),
            "keep_alive": str(routing.get("keep_alive", defaults["keep_alive"]))[:16],
        }

        experience = settings.get("experience", {})
        if not isinstance(experience, dict):
            experience = {}
        experience_defaults = DEFAULT_SETTINGS["experience"]
        responses = []
        raw_responses = experience.get("instant_responses")
        if isinstance(raw_responses, list):
            for index, item in enumerate(raw_responses[:30]):
                if not isinstance(item, dict):
                    continue
                triggers = item.get("triggers", [])
                if isinstance(triggers, str):
                    triggers = [triggers]
                clean_triggers = []
                if isinstance(triggers, list):
                    for trigger in triggers[:12]:
                        clean = str(trigger).strip()[:60]
                        if clean and clean not in clean_triggers:
                            clean_triggers.append(clean)
                response = str(item.get("response", "")).strip()[:180]
                if clean_triggers and response:
                    responses.append({
                        "id": str(item.get("id") or f"instant-{index + 1}")[:32],
                        "triggers": clean_triggers,
                        "response": response,
                    })
        if not responses:
            responses = copy.deepcopy(DEFAULT_INSTANT_RESPONSES)
        time_zone = str(
            experience.get("time_zone", experience_defaults["time_zone"])
        ).strip()[:64]
        thinking_cue = str(
            experience.get("thinking_cue", experience_defaults["thinking_cue"])
        ).strip()[:80]
        local_cue = str(
            experience.get("local_cue", experience_defaults["local_cue"])
        ).strip()[:40]
        if source_schema < 3 and local_cue.casefold().rstrip(".") == "a ver":
            local_cue = ""
        output["experience"] = {
            "instant_enabled": ProductSettings._as_bool(
                experience.get("instant_enabled"), True
            ),
            "thinking_cue_enabled": ProductSettings._as_bool(
                experience.get("thinking_cue_enabled"), True
            ),
            "voice_cache_enabled": ProductSettings._as_bool(
                experience.get("voice_cache_enabled"), True
            ),
            "time_zone": time_zone or experience_defaults["time_zone"],
            "local_cue": local_cue,
            "thinking_cue": thinking_cue or experience_defaults["thinking_cue"],
            "instant_responses": responses,
        }

        actions = settings.get("quick_actions")
        output["quick_actions"] = []
        if isinstance(actions, list):
            for index, action in enumerate(actions[:6]):
                if not isinstance(action, dict):
                    continue
                label = str(action.get("label", "")).strip()[:22]
                prompt = str(action.get("prompt", "")).strip()[:400]
                if label and prompt:
                    output["quick_actions"].append({
                        "id": str(action.get("id") or f"action-{index + 1}")[:32],
                        "label": label,
                        "prompt": prompt,
                    })
        if not output["quick_actions"]:
            output["quick_actions"] = copy.deepcopy(DEFAULT_QUICK_ACTIONS)
        return output

    @staticmethod
    def _bounded_int(value, minimum, maximum, default):
        try:
            return max(minimum, min(maximum, int(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_bool(value, default):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "si"}
        return default if value is None else bool(value)
