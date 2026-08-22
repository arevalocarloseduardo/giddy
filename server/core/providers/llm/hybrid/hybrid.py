import json
import hashlib
import re
import threading
import time
from dataclasses import dataclass

import httpx

from config.logger import setup_logging
from core.product_settings import ProductSettings
from core.providers.llm.base import LLMProviderBase
from core.providers.llm.hybrid.reflex import ReflexEngine
from core.providers.llm.openai.openai import LLMProvider as OpenAIProvider


TAG = __name__
logger = setup_logging()


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str


class GiddyRouter:
    POWER_PATTERNS = (
        ("pedido explicito", r"\b(usa|usá|utiliza)\s+(hermes|el modelo (mejor|potente)|razonamiento)\b|\bpensalo bien\b"),
        ("accion real", r"\b(agenda|agendá|recordame|avisame|reserv[áa]|cancel[áa]|envi[áa]|mand[áa]|public[áa]|sub[íi]|descarg[áa]|compr[áa]|pag[áa]|llam[áa]|escribile|configur[áa]|conect[áa]|sincroniz[áa])\b"),
        ("informacion actual", r"\b(hoy|mañana|ahora|actual|ultimo|último|reciente|noticias|clima|pronostico|pronóstico|precio|cotizacion|cotización|dolar|dólar|hora|fecha)\b"),
        ("datos personales", r"\b(mi agenda|mi calendario|mis tareas|mis ventas|mis gastos|mi negocio|mis archivos|mis correos|mis mensajes|te acordas|te acordás|recordas|recordás)\b"),
        ("herramienta o archivo", r"\b(internet|web|google|calendario|correo|email|gmail|whatsapp|telegram|archivo|documento|pdf|excel|planilla|foto|imagen|audio|video|link|enlace|carpeta|base de datos)\b"),
        ("trabajo complejo", r"\b(analiz[áa]|investig[áa]|compar[áa]|planific[áa]|diagnostic[áa]|program[áa]|implement[áa]|constru[íi]|diseñ[áa]|estrategia|arquitectura|informe completo|paso a paso|en profundidad)\b"),
        ("decision o riesgo", r"\b(decid(?:ir|[íi]|[ae])|evalu[áa]|audit[áa]|optimiz[áa]|resolv(?:er|[ée])|solucion[áa]|propuesta|presupuesto|campaña|contrato|legal|medic[oa]|salud|finanzas?|inversion|inversión)\b"),
        ("creacion entregable", r"\b(cre[áa]|gener[áa]|arm[áa]|edit[áa]|modific[áa]|prepar[áa])\b.{0,40}\b(video|imagen|foto|archivo|documento|pdf|planilla|presentacion|presentación|codigo|código|app|sitio|informe)\b"),
    )
    LOCAL_PATTERNS = (
        ("saludo", r"^(hola|buenas|buen dia|buen día|buenas tardes|buenas noches|hey|ey|que tal|qué tal)[!,. ]*$"),
        ("cortesia", r"\b(gracias|muchas gracias|por favor|chau|adios|adiós|hasta luego|perfecto|genial|dale|ok|okay|listo)\b"),
        ("charla", r"\b(como estas|cómo estás|que haces|qué hacés|quien sos|quién sos|estoy aburrid|acompañame|acompañáme)\b"),
        ("entretenimiento breve", r"\b(chiste|adivinanza|acertijo|cuento corto|historia corta|trabalenguas)\b"),
        ("lenguaje simple", r"\b(que significa|qué significa|como se dice|cómo se dice|traduci|traducí|sinonimo|sinónimo|deletrea)\b"),
    )

    def choose(self, text, mode="balanced"):
        normalized = self._normalize(text)
        if not normalized:
            return RouteDecision("local", "mensaje breve")

        if re.search(r"\b(usa|usá)\s+(local|modo local)\b", normalized):
            return RouteDecision("local", "pedido explicito")

        for reason, pattern in self.POWER_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return RouteDecision("power", reason)

        if self._looks_like_calculation(normalized):
            return RouteDecision("power", "calculo")
        if len(normalized) > 280:
            return RouteDecision("power", "pedido largo")

        for reason, pattern in self.LOCAL_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return RouteDecision("local", reason)

        if mode == "max":
            return RouteDecision("power", "modo maxima calidad")
        if mode == "eco":
            return RouteDecision("local", "modo ahorro")
        if len(normalized) <= 180:
            return RouteDecision("local", "consulta cotidiana")
        return RouteDecision("power", "consulta amplia")

    @staticmethod
    def _normalize(text):
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    @staticmethod
    def _looks_like_calculation(text):
        if not re.search(r"\d", text):
            return False
        return bool(re.search(r"(?:\d\s*[-+*/x%]\s*\d)|\b(porcentaje|cuanto|cuánto|sum[áa]|rest[áa]|multiplic[áa]|divid[íi])\b", text))


class LLMProvider(LLMProviderBase):
    SAFE_ENTERTAINMENT = {
        "chiste": (
            "¿Que hace una computadora cuando tiene frio? Cierra Windows.",
            "¿Por que el libro de matematica estaba triste? Porque tenia demasiados problemas.",
            "¿Que le dijo una pared a la otra? Nos vemos en la esquina.",
            "¿Como se despiden los quimicos? Acido un placer.",
        ),
        "adivinanza": (
            "Adivinanza: tengo agujas y no se coser, tengo numeros y no se leer. ¿Que soy? Un reloj.",
            "Adivinanza: cuanto mas le sacas, mas grande se vuelve. ¿Que es? Un agujero.",
        ),
        "trabalenguas": (
            "Tres tristes tigres tragan trigo en un trigal.",
            "Pablito clavo un clavito. ¿Que clavito clavo Pablito?",
        ),
        "cuento": (
            "Una taza se cansó de esperar el cafe y salio a buscarlo. Volvio llena de historias y con aroma a aventura.",
            "Una lamparita queria conocer la noche. Se apago un minuto y descubrio que las estrellas tambien saben iluminar.",
        ),
    }
    SAFE_ENTERTAINMENT_ALIASES = (
        ("chiste", "chiste"),
        ("adivinanza", "adivinanza"),
        ("acertijo", "adivinanza"),
        ("trabalenguas", "trabalenguas"),
        ("cuento", "cuento"),
        ("historia", "cuento"),
    )
    SPOKEN_TRANSLATION = str.maketrans({
        "ż": "¿",
        "Ż": "¿",
        "Ą": "¡",
        "ą": "¡",
        "—": ", ",
        "–": "-",
        "…": "...",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "\n": " ",
        "\r": " ",
        "\t": " ",
    })
    UNSUPPORTED_SPOKEN_CHARS = re.compile(
        r"[^A-Za-z0-9 áéíóúÁÉÍÓÚüÜñÑ¿¡.,;:!?()'\"%+\-=/]"
    )
    LOCAL_SYSTEM_PROMPT = (
        "Sos Giddy, un asistente de voz argentino cercano, agil y confiable. "
        "Responde en espanol rioplatense con voseo natural. Usa una o dos frases cortas, "
        "texto plano, sin markdown y solo con caracteres normales del espanol. "
        "No escribas risas como jaja, jeje o similares; responde directamente. "
        "Sos un asistente personal: no ofrezcas historias, chistes, anecdotas, juegos "
        "ni dialogos salvo que el usuario los pida de forma explicita. No cierres con "
        "propuestas de entretenimiento ni preguntas como te animas. "
        "El humor debe ser amable: nunca bromees sobre muerte, enfermedad, violencia ni tragedias. "
        "No inventes datos actuales ni afirmes haber realizado acciones."
    )

    def __init__(self, config):
        self.config = config
        self.settings = ProductSettings(config.get("settings_path"))
        self.router = GiddyRouter()
        self.reflex = ReflexEngine()
        self.power = OpenAIProvider(config.get("power", {}))
        self.local_client = httpx.Client(timeout=httpx.Timeout(30, connect=2))
        self._thinking_cue_lock = threading.Lock()
        self._last_thinking_cue_at = {}

    def response(self, session_id, dialogue, **kwargs):
        current = self.settings.load()
        text = self._last_user_text(dialogue)
        reflex = self.reflex.match(text, current)
        if reflex:
            self._record_instant_response(session_id, text, reflex)
            yield reflex.text
            return
        decision = self.router.choose(text, current["mode"])
        early_cue = ""

        if decision.route == "local":
            shortcut = self._safe_entertainment_response(session_id, text, decision)
            if shortcut:
                yield shortcut
                return
            early_cue = self._local_cue(text, current)
            if early_cue:
                yield early_cue + " "
            emitted = False
            try:
                for token in self._local_response(
                    session_id,
                    dialogue,
                    current,
                    decision,
                    cue=bool(early_cue),
                ):
                    emitted = True
                    yield token
                return
            except Exception as exc:
                logger.bind(tag=TAG).warning(f"Modelo local no disponible: {exc}")
                if emitted:
                    raise
                decision = RouteDecision("power", "respaldo automatico")

        cue = "" if early_cue else self._thinking_cue(text, current, session_id)
        if cue:
            yield cue + " "
        yield from self._power_response(
            session_id,
            dialogue,
            current,
            decision,
            cue=bool(early_cue or cue),
            **kwargs,
        )

    def response_with_functions(self, session_id, dialogue, functions=None, **kwargs):
        current = self.settings.load()
        text = self._last_user_text(dialogue)
        reflex = self.reflex.match(text, current)
        if reflex:
            self._record_instant_response(session_id, text, reflex)
            yield reflex.text, None
            return
        trimmed = self._trim_dialogue(
            dialogue,
            current["routing"]["power_context_chars"],
            keep_system=True,
        )
        started = time.perf_counter()
        output_chars = 0
        request_options = dict(kwargs)
        request_options["max_tokens"] = current["routing"]["power_max_tokens"]
        cue = self._thinking_cue(text, current, session_id)
        if cue:
            output_chars += len(cue)
            yield cue + " ", None
        try:
            for content, tool_calls in self.power.response_with_functions(
                session_id,
                trimmed,
                functions=functions,
                **request_options,
            ):
                if content:
                    output_chars += len(content)
                yield content, tool_calls
        finally:
            self.settings.append_route_metric({
                "route": "power",
                "reason": "herramientas",
                "session_id": session_id,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "input_chars": sum(len(str(item.get("content", ""))) for item in trimmed),
                "output_chars": output_chars,
                "cue": bool(cue),
            })

    def _local_response(self, session_id, dialogue, current, decision, cue=False):
        routing = current["routing"]
        local_dialogue = self._trim_dialogue(
            dialogue,
            routing["local_context_chars"],
            keep_system=False,
        )
        local_dialogue.insert(0, {"role": "system", "content": self.LOCAL_SYSTEM_PROMPT})
        payload = {
            "model": routing["local_model"],
            "messages": local_dialogue,
            "stream": True,
            "think": False,
            "keep_alive": routing["keep_alive"],
            "options": {
                "temperature": 0.25,
                "num_ctx": 4096,
                "num_predict": routing["local_max_tokens"],
            },
        }
        url = routing["local_url"].rstrip("/") + "/api/chat"
        started = time.perf_counter()
        output_chars = 0
        prompt_tokens = 0
        output_tokens = 0
        failed = True
        timeout = httpx.Timeout(routing["local_timeout_seconds"], connect=2)

        try:
            with self.local_client.stream("POST", url, json=payload, timeout=timeout) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    content = self._sanitize_spoken_text(
                        chunk.get("message", {}).get("content", "")
                    )
                    if content:
                        output_chars += len(content)
                        yield content
                    if chunk.get("done"):
                        prompt_tokens = int(chunk.get("prompt_eval_count", 0) or 0)
                        output_tokens = int(chunk.get("eval_count", 0) or 0)
                failed = False
        finally:
            self.settings.append_route_metric({
                "route": "local",
                "reason": decision.reason,
                "session_id": session_id,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "input_chars": sum(len(str(item.get("content", ""))) for item in local_dialogue),
                "output_chars": output_chars,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "fallback": failed,
                "cue": cue,
            })

    def _power_response(self, session_id, dialogue, current, decision, cue=False, **kwargs):
        routing = current["routing"]
        trimmed = self._trim_dialogue(dialogue, routing["power_context_chars"], keep_system=True)
        started = time.perf_counter()
        output_chars = 0
        request_options = dict(kwargs)
        request_options["max_tokens"] = routing["power_max_tokens"]
        try:
            for token in self.power.response(
                session_id,
                trimmed,
                **request_options,
            ):
                output_chars += len(token)
                yield token
        finally:
            self.settings.append_route_metric({
                "route": "power",
                "reason": decision.reason,
                "session_id": session_id,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "input_chars": sum(len(str(item.get("content", ""))) for item in trimmed),
                "output_chars": output_chars,
                "fallback": decision.reason == "respaldo automatico",
                "cue": cue,
            })

    @staticmethod
    def _last_user_text(dialogue):
        for item in reversed(dialogue or []):
            if item.get("role") == "user":
                content = item.get("content", "")
                return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        return ""

    def _safe_entertainment_response(self, session_id, text, decision):
        if decision.reason != "entretenimiento breve":
            return None
        normalized = self.router._normalize(text)
        category = next(
            (category for trigger, category in self.SAFE_ENTERTAINMENT_ALIASES if trigger in normalized),
            None,
        )
        if not category:
            return None
        choices = self.SAFE_ENTERTAINMENT[category]
        digest = hashlib.sha256(f"{session_id}:{normalized}".encode()).digest()
        answer = choices[int.from_bytes(digest[:2], "big") % len(choices)]
        self.settings.append_route_metric({
            "route": "local",
            "reason": "entretenimiento curado",
            "session_id": session_id,
            "latency_ms": 0,
            "input_chars": len(str(text or "")),
            "output_chars": len(answer),
            "prompt_tokens": 0,
            "output_tokens": 0,
            "fallback": False,
        })
        return answer

    def _record_instant_response(self, session_id, text, reflex):
        self.settings.append_route_metric({
            "route": "instant",
            "reason": reflex.reason,
            "session_id": session_id,
            "latency_ms": 0,
            "input_chars": len(str(text or "")),
            "output_chars": len(reflex.text),
            "prompt_tokens": 0,
            "output_tokens": 0,
            "fallback": False,
        })

    def _thinking_cue(self, text, current, session_id=None):
        cue = self._cue(text, current, "thinking_cue", "Dame un segundo.")
        if not cue or not session_id:
            return cue

        now = time.monotonic()
        cooldown = 20.0
        with self._thinking_cue_lock:
            previous = self._last_thinking_cue_at.get(session_id, 0.0)
            if now - previous < cooldown:
                return ""
            self._last_thinking_cue_at[session_id] = now
            if len(self._last_thinking_cue_at) > 512:
                cutoff = now - 3600.0
                self._last_thinking_cue_at = {
                    key: timestamp
                    for key, timestamp in self._last_thinking_cue_at.items()
                    if timestamp >= cutoff
                }
        return cue

    def _local_cue(self, text, current):
        return self._cue(text, current, "local_cue", "")

    def _cue(self, text, current, key, default):
        experience = current.get("experience", {})
        if not experience.get("thinking_cue_enabled", True):
            return ""
        normalized = self.router._normalize(text)
        if re.search(r"\b(exactamente|responde solo|solo responde|sin agregar nada)\b", normalized):
            return ""
        return str(experience.get(key, default)).strip()

    @classmethod
    def _sanitize_spoken_text(cls, text):
        normalized = str(text or "").translate(cls.SPOKEN_TRANSLATION)
        return cls.UNSUPPORTED_SPOKEN_CHARS.sub("", normalized)

    @staticmethod
    def _trim_dialogue(dialogue, char_budget, keep_system):
        system = None
        candidates = []
        for item in dialogue or []:
            role = item.get("role")
            content = item.get("content", "")
            if role == "system" and system is None:
                system = {"role": "system", "content": str(content)[:1800]}
            elif role in {"user", "assistant"}:
                candidates.append({"role": role, "content": str(content)})

        selected = []
        used = len(system["content"]) if keep_system and system else 0
        for item in reversed(candidates):
            remaining = char_budget - used
            if remaining <= 0:
                break
            content = item["content"]
            if len(content) > remaining:
                content = content[-remaining:]
            selected.append({"role": item["role"], "content": content})
            used += len(content)
        selected.reverse()
        if keep_system and system:
            selected.insert(0, system)
        return selected
