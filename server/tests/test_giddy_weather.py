import json
import unittest
from unittest.mock import AsyncMock, patch

from core.providers.intent.giddy_intent.giddy_intent import IntentProvider
from plugins_func.functions import get_giddy_weather as weather_module
from plugins_func.functions.get_giddy_weather import format_weather_response


class GiddyWeatherIntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_routes_temperature_question_to_default_location(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(
                None, [], "Cuantos grados va a hacer manana?"
            )
        )

        arguments = result["function_call"]["arguments"]
        self.assertEqual(result["function_call"]["name"], "get_giddy_weather")
        self.assertEqual(arguments["location"], "")
        self.assertEqual(arguments["day"], "tomorrow")

    async def test_repairs_live_helado_asr_confusion(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(
                None, [], "Cuanto helado va a ser manana?"
            )
        )

        self.assertEqual(result["function_call"]["name"], "get_giddy_weather")
        self.assertEqual(result["function_call"]["arguments"]["location"], "")

    async def test_routes_rain_question_to_weather(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(None, [], "Va a llover manana?")
        )

        self.assertEqual(result["function_call"]["name"], "get_giddy_weather")

    async def test_does_not_confuse_an_ice_cream_request_with_weather(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(None, [], "Quiero un helado")
        )

        self.assertEqual(result["function_call"]["name"], "continue_chat")

    async def test_routes_current_weather_without_llm(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(None, [], "Como esta el clima hoy?")
        )

        self.assertEqual(
            result["function_call"]["name"], "get_giddy_weather"
        )
        self.assertEqual(result["function_call"]["arguments"]["day"], "today")

    async def test_extracts_location_and_tomorrow(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(
                None, [], "Que pronostico hay para Mar del Plata mañana?"
            )
        )

        arguments = result["function_call"]["arguments"]
        self.assertEqual(arguments["location"], "Mar del Plata")
        self.assertEqual(arguments["day"], "tomorrow")

    async def test_does_not_route_unrelated_use_of_time_word(self):
        result = json.loads(
            await IntentProvider({}).detect_intent(
                None, [], "Necesito tiempo para terminar este trabajo"
            )
        )

        self.assertEqual(result["function_call"]["name"], "continue_chat")


class GiddyWeatherFormattingTests(unittest.TestCase):
    def setUp(self):
        self.forecast = {
            "current": {"temperature_2m": 9.6, "weather_code": 2},
            "daily": {
                "weather_code": [2, 61],
                "temperature_2m_max": [15.2, 13.8],
                "temperature_2m_min": [7.4, 8.1],
                "precipitation_probability_max": [20, 70],
            },
        }

    def test_formats_short_current_weather(self):
        response = format_weather_response("La Plata", self.forecast, "today")

        self.assertIn("hay 10 grados", response)
        self.assertIn("20 por ciento", response)
        self.assertIn("abrigo", response)

    def test_formats_tomorrow_and_rain_advice(self):
        response = format_weather_response("La Plata", self.forecast, "tomorrow")

        self.assertIn("Mañana", response)
        self.assertIn("70 por ciento", response)
        self.assertIn("paraguas", response)


class GiddyWeatherCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        weather_module.WEATHER_CACHE.clear()

    async def test_force_refresh_replaces_a_warm_forecast(self):
        config = {"cache_seconds": 600, "timeout_seconds": 4}
        location = {
            "latitude": -34.9205,
            "longitude": -57.9536,
            "timezone": "America/Argentina/Buenos_Aires",
        }
        response = {"current": {}, "daily": {}}

        with patch.object(
            weather_module,
            "_request_json",
            new=AsyncMock(return_value=response),
        ) as request:
            await weather_module._fetch_forecast(config, location)
            await weather_module._fetch_forecast(config, location)
            await weather_module._fetch_forecast(
                config, location, force_refresh=True
            )

        self.assertEqual(request.await_count, 2)


if __name__ == "__main__":
    unittest.main()
