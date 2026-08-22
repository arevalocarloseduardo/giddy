import asyncio
import time
from typing import TYPE_CHECKING

import aiohttp

from plugins_func.register import Action, ActionResponse, ToolType, register_function

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_CACHE = {}
LOCATION_CACHE = {}

WEATHER_CODES = {
    0: "el cielo esta despejado",
    1: "esta mayormente despejado",
    2: "esta parcialmente nublado",
    3: "esta nublado",
    45: "hay niebla",
    48: "hay niebla",
    51: "hay una llovizna leve",
    53: "hay llovizna",
    55: "hay llovizna intensa",
    56: "hay llovizna helada",
    57: "hay llovizna helada intensa",
    61: "llueve de forma leve",
    63: "esta lloviendo",
    65: "llueve fuerte",
    66: "hay lluvia helada",
    67: "hay lluvia helada intensa",
    71: "nieva de forma leve",
    73: "esta nevando",
    75: "nieva fuerte",
    77: "caen granos de nieve",
    80: "hay chaparrones leves",
    81: "hay chaparrones",
    82: "hay chaparrones fuertes",
    85: "hay chaparrones de nieve",
    86: "hay chaparrones fuertes de nieve",
    95: "hay tormenta",
    96: "hay tormenta con granizo",
    99: "hay tormenta fuerte con granizo",
}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}

GET_GIDDY_WEATHER_DESC = {
    "type": "function",
    "function": {
        "name": "get_giddy_weather",
        "description": "Da el clima actual o el pronostico de manana de forma breve y directa.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Ciudad opcional. Vacio usa la ubicacion configurada.",
                },
                "day": {
                    "type": "string",
                    "enum": ["today", "tomorrow"],
                },
            },
        },
    },
}


def _cache_get(cache, key):
    item = cache.get(key)
    if not item or item["expires_at"] <= time.monotonic():
        cache.pop(key, None)
        return None
    return item["value"]


def _cache_set(cache, key, value, ttl_seconds):
    cache[key] = {
        "value": value,
        "expires_at": time.monotonic() + max(1, int(ttl_seconds)),
    }


def _clean_location(value):
    return " ".join(str(value or "").strip(" .,:;!?¿¡").split())[:80]


async def _request_json(url, params, timeout_seconds):
    timeout = aiohttp.ClientTimeout(total=timeout_seconds, connect=min(2, timeout_seconds))
    headers = {"User-Agent": "Giddy voice assistant/2.4"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()


async def _resolve_location(config, requested_location):
    default_name = str(config.get("default_location", "La Plata")).strip() or "La Plata"
    default_value = {
        "name": default_name,
        "latitude": float(config.get("latitude", -34.9205)),
        "longitude": float(config.get("longitude", -57.9536)),
        "timezone": str(
            config.get("timezone", "America/Argentina/Buenos_Aires")
        ),
    }
    location = _clean_location(requested_location)
    normalized = location.casefold()
    use_default = (
        not location
        or normalized in {"aca", "acá", "aqui", "aquí", "mi ubicacion", "mi ubicación"}
        or default_name.casefold() in normalized
    )
    if use_default:
        return default_value

    cached = _cache_get(LOCATION_CACHE, normalized)
    if cached:
        return cached

    data = await _request_json(
        GEOCODING_URL,
        {"name": location, "count": 1, "language": "es", "format": "json"},
        float(config.get("timeout_seconds", 4)),
    )
    results = data.get("results") or []
    if not results:
        raise ValueError(f"No encontre la ubicacion {location}")
    first = results[0]
    resolved = {
        "name": str(first.get("name") or location),
        "latitude": float(first["latitude"]),
        "longitude": float(first["longitude"]),
        "timezone": str(first.get("timezone") or default_value["timezone"]),
    }
    _cache_set(LOCATION_CACHE, normalized, resolved, 86400)
    return resolved


async def _fetch_forecast(config, location, force_refresh=False):
    cache_key = (
        round(location["latitude"], 3),
        round(location["longitude"], 3),
        location["timezone"],
    )
    cached = None if force_refresh else _cache_get(WEATHER_CACHE, cache_key)
    if cached is not None:
        return cached

    data = await _request_json(
        FORECAST_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": (
                "temperature_2m,apparent_temperature,precipitation,"
                "weather_code,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": location["timezone"],
            "forecast_days": 2,
        },
        float(config.get("timeout_seconds", 4)),
    )
    _cache_set(
        WEATHER_CACHE,
        cache_key,
        data,
        int(config.get("cache_seconds", 600)),
    )
    return data


async def maintain_weather_cache(config):
    """Keep the default location warm so voice requests avoid API latency."""
    refresh_seconds = max(
        60,
        int(float(config.get("cache_seconds", 600)) * 0.8),
    )
    while True:
        try:
            resolved = await _resolve_location(config, "")
            await _fetch_forecast(config, resolved, force_refresh=True)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
            # A voice request still has its own bounded live fallback.
            pass
        await asyncio.sleep(refresh_seconds)


def _number(value, default=0):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def format_weather_response(location_name, forecast, day="today"):
    current = forecast.get("current", {})
    daily = forecast.get("daily", {})
    index = 1 if day == "tomorrow" else 0

    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    rain_probabilities = daily.get("precipitation_probability_max") or []
    if len(codes) <= index or len(highs) <= index or len(lows) <= index:
        raise ValueError("El pronostico llego incompleto")

    code = _number(codes[index], -1)
    high = _number(highs[index])
    low = _number(lows[index])
    rain = _number(rain_probabilities[index] if len(rain_probabilities) > index else 0)
    condition = WEATHER_CODES.get(code, "el tiempo esta variable")

    if day == "tomorrow":
        response = (
            f"Mañana en {location_name} {condition}. "
            f"La maxima sera de {high} grados, la minima de {low}, "
            f"y hay {rain} por ciento de probabilidad de lluvia."
        )
    else:
        current_code = _number(current.get("weather_code"), code)
        condition = WEATHER_CODES.get(current_code, condition)
        temperature = _number(current.get("temperature_2m"), high)
        response = (
            f"En {location_name} hay {temperature} grados y {condition}. "
            f"Hay {rain} por ciento de probabilidad de lluvia."
        )

    advice = []
    if rain >= 40 or code in RAIN_CODES:
        advice.append("paraguas")
    if low <= 10:
        advice.append("algo de abrigo")
    if advice:
        response += " Conviene llevar " + " y ".join(advice) + "."
    return response


@register_function("get_giddy_weather", GET_GIDDY_WEATHER_DESC, ToolType.SYSTEM_CTL)
async def get_giddy_weather(
    conn: "ConnectionHandler", location: str = "", day: str = "today"
):
    config = conn.config.get("plugins", {}).get("get_giddy_weather", {})
    selected_day = "tomorrow" if str(day).lower() == "tomorrow" else "today"
    try:
        resolved = await _resolve_location(config, location)
        forecast = await _fetch_forecast(config, resolved)
        response = format_weather_response(resolved["name"], forecast, selected_day)
        return ActionResponse(Action.RESPONSE, response, response)
    except Exception as exc:
        conn.logger.bind(tag=__name__).warning(f"Clima directo no disponible: {exc}")
        response = "No pude consultar el clima en este momento. Proba de nuevo en un rato."
        return ActionResponse(Action.ERROR, str(exc), response)
