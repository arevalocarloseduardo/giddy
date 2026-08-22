import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ReflexReply:
    text: str
    reason: str


class ReflexEngine:
    TIME_REQUESTS = {
        "hora",
        "que hora es",
        "que hora es ahora",
        "decime la hora",
        "me decis la hora",
        "me podes decir la hora",
    }
    DATE_REQUESTS = {
        "que dia es",
        "que fecha es",
        "que dia es hoy",
        "cual es la fecha",
        "decime la fecha",
    }
    WEEKDAYS = (
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    )
    MONTHS = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    NUMBERS = {
        0: "cero",
        1: "uno",
        2: "dos",
        3: "tres",
        4: "cuatro",
        5: "cinco",
        6: "seis",
        7: "siete",
        8: "ocho",
        9: "nueve",
        10: "diez",
        11: "once",
        12: "doce",
        13: "trece",
        14: "catorce",
        15: "quince",
        16: "dieciséis",
        17: "diecisiete",
        18: "dieciocho",
        19: "diecinueve",
        20: "veinte",
        21: "veintiuno",
        22: "veintidós",
        23: "veintitrés",
        24: "veinticuatro",
        25: "veinticinco",
        26: "veintiséis",
        27: "veintisiete",
        28: "veintiocho",
        29: "veintinueve",
    }
    TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta"}

    def match(self, text, settings, now=None):
        experience = settings.get("experience", {})
        if not experience.get("instant_enabled", True):
            return None

        normalized = self.normalize(text)
        if not normalized:
            return None

        if normalized in self.TIME_REQUESTS:
            current = now or self._now(experience.get("time_zone"))
            return ReflexReply(self._time_response(current), "hora local")
        if normalized in self.DATE_REQUESTS:
            current = now or self._now(experience.get("time_zone"))
            return ReflexReply(self._date_response(current), "fecha local")

        for item in experience.get("instant_responses", []):
            if any(self.normalize(trigger) == normalized for trigger in item.get("triggers", [])):
                return ReflexReply(str(item.get("response", "")), "respuesta instantánea")
        return None

    @staticmethod
    def normalize(text):
        decomposed = unicodedata.normalize("NFKD", str(text or "").casefold())
        without_accents = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", without_accents)).strip()

    @staticmethod
    def _now(time_zone):
        try:
            return datetime.now(ZoneInfo(str(time_zone)))
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            return datetime.now().astimezone()

    @classmethod
    def _number(cls, value):
        if value in cls.NUMBERS:
            return cls.NUMBERS[value]
        tens = value // 10 * 10
        remainder = value % 10
        return f"{cls.TENS[tens]} y {cls.NUMBERS[remainder]}"

    @classmethod
    def _time_response(cls, current):
        spoken_hour = 12 if current.hour == 0 else current.hour
        hour = cls._number(spoken_hour)
        if spoken_hour == 1:
            prefix = "Es la una"
        else:
            prefix = f"Son las {hour}"
        if current.minute == 0:
            return f"{prefix} en punto."
        if current.minute == 15:
            return f"{prefix} y cuarto."
        if current.minute == 30:
            return f"{prefix} y media."
        return f"{prefix} y {cls._number(current.minute)}."

    @classmethod
    def _date_response(cls, current):
        weekday = cls.WEEKDAYS[current.weekday()]
        month = cls.MONTHS[current.month - 1]
        return f"Hoy es {weekday} {cls._number(current.day)} de {month}."
