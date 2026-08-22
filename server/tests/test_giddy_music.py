import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.providers.intent.giddy_intent.giddy_intent import IntentProvider
from plugins_func.functions.play_music import (
    _extract_song_name,
    _find_best_match,
    _announcement,
    _cached_youtube_result,
    _is_youtube_url,
    initialize_music_handler,
    _resolve_youtube_query,
    _youtube_match_filter,
    _youtube_source,
)
from core.utils.music_queries import normalize_music_query


class GiddyMusicIntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_recognizes_live_reproducime_command(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(None, [], "reproducime la noche sin ti")
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "la noche sin ti",
        )

    async def test_recognizes_conversational_youtube_request(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "No, necesito que me reproduzcas en Youtube los redonditos de ricota.",
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "los redonditos de ricota",
        )

    async def test_repairs_noisy_rock_request(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "No, quiero que me reproduzco a una cancion que sea una de rock.",
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "rock",
        )

    async def test_recognizes_argentine_music_command_without_llm(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(None, [], "Poneme De musica ligera de Soda Stereo")
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "De musica ligera de Soda Stereo",
        )

    async def test_regular_question_continues_to_chat(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(None, [], "Que musica te gusta?")
        )

        self.assertEqual(result["function_call"]["name"], "continue_chat")

    async def test_recovers_title_from_noisy_spoken_followup(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(None, [], "Un si el tema de perdoname")
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "perdoname",
        )

    async def test_remembers_incomplete_music_request_for_followup(self):
        provider = IntentProvider({})
        conn = SimpleNamespace(config={})

        first = json.loads(await provider.detect_intent(conn, [], "Voy a reproducir"))
        self.assertGreater(conn.giddy_pending_music_until, 0)
        incomplete = json.loads(
            await provider.detect_intent(conn, [], "Giddy reproduce")
        )
        still_incomplete = json.loads(
            await provider.detect_intent(conn, [], "Lo que reproduzcas")
        )
        second = json.loads(
            await provider.detect_intent(conn, [], "Un si el tema de perdoname")
        )

        self.assertEqual(first["function_call"]["name"], "continue_chat")
        self.assertEqual(incomplete["function_call"]["name"], "continue_chat")
        self.assertEqual(still_incomplete["function_call"]["name"], "continue_chat")
        self.assertEqual(second["function_call"]["name"], "play_music")
        self.assertEqual(
            second["function_call"]["arguments"]["song_name"],
            "perdoname",
        )

    async def test_routes_known_song_alias_without_repeating_play_command(self):
        provider = IntentProvider({})
        conn = SimpleNamespace(
            config={
                "plugins": {
                    "play_music": {
                        "youtube_aliases": {
                            "daddy yankee llamado de emergencia": {
                                "url": "https://www.youtube.com/watch?v=KS8K72jwR70"
                            }
                        }
                    }
                }
            }
        )

        result = json.loads(
            await provider.detect_intent(conn, [], "Daddy Yankee llamado de emergencia")
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "Daddy Yankee Llamado de Emergencia",
        )

    async def test_routes_song_followup_after_failed_music_attempt(self):
        provider = IntentProvider({})
        conn = SimpleNamespace(
            config={},
            giddy_pending_music_until=time.monotonic() + 30,
        )

        result = json.loads(
            await provider.detect_intent(conn, [], "Daddy Yankee llamado emergencia")
        )

        self.assertEqual(result["function_call"]["name"], "play_music")

    async def test_understands_polite_youtube_request_from_live_audio(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "puede reproducir una canción de youtube niche en nuestro sueño",
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "Grupo Niche en nuestro sueño",
        )

    async def test_repairs_niche_asr_confusion(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None, [], "Reproducí la canción de Nietzsche"
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "Grupo Niche",
        )

    async def test_understands_search_then_play_command(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "Busca una canción que se llama Grupo Nietzsche y reproducíla.",
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "Grupo Niche",
        )

    async def test_understands_accented_youtube_request(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None, [], "Poné música de YouTube Ji ji ji de los Redondos"
            )
        )

        self.assertEqual(result["function_call"]["name"], "play_music")
        self.assertEqual(
            result["function_call"]["arguments"]["song_name"],
            "Ji ji ji de los Redondos",
        )


class MusicHelpersTests(unittest.TestCase):
    def test_repairs_live_daddy_yankee_asr_confusion(self):
        self.assertEqual(
            normalize_music_query("llamada emergencia baby de Daddy Junkins"),
            "Llamado de Emergencia de Daddy Yankee",
        )

    def test_uses_one_short_announcement_before_playback(self):
        self.assertEqual(
            _announcement("Grupo Niche - Nuestro Sueño"),
            "Pongo Grupo Niche - Nuestro Sueño.",
        )

    def test_extracts_song_name_from_spoken_command(self):
        self.assertEqual(
            _extract_song_name("Reproduci musica Persiana Americana"),
            "Persiana Americana",
        )

    def test_extracts_song_after_youtube_qualifier(self):
        self.assertEqual(
            _extract_song_name("Reproducí desde yutub Seminare de Serú Girán"),
            "Seminare de Serú Girán",
        )

    def test_extracts_polite_music_request(self):
        self.assertEqual(
            _extract_song_name(
                "¿Podés reproducir una canción de YouTube Niche Nuestro Sueño?"
            ),
            "Grupo Niche Nuestro Sueño",
        )

    def test_repairs_niche_in_tool_arguments(self):
        self.assertEqual(
            _extract_song_name("Reproducí la canción de Nietzsche"),
            "Grupo Niche",
        )

    def test_prefers_close_local_match(self):
        self.assertEqual(
            _find_best_match(
                "persiana americana",
                ["Soda Stereo - Persiana Americana.mp3", "otra.wav"],
            ),
            "Soda Stereo - Persiana Americana.mp3",
        )

    def test_only_accepts_youtube_urls_as_direct_sources(self):
        url = "https://www.youtube.com/watch?v=BaW_jenozKc"
        self.assertTrue(_is_youtube_url(url))
        self.assertEqual(_youtube_source(url), url)
        self.assertEqual(_youtube_source("una cancion"), "ytsearch1:una cancion")

    def test_rejects_live_and_overlong_audio(self):
        match = _youtube_match_filter(900)
        self.assertIsNotNone(match({"is_live": True}))
        self.assertIsNotNone(match({"duration": 901}))
        self.assertIsNone(match({"duration": 180}))

    def test_resolves_known_niche_alias_and_biases_regular_searches(self):
        from plugins_func.functions import play_music as music_module

        previous = music_module.MUSIC_CACHE
        try:
            music_module.MUSIC_CACHE = {
                "youtube_aliases": {
                    "grupo niche": "https://www.youtube.com/watch?v=YmQiUg75q84"
                }
            }
            self.assertEqual(
                _resolve_youtube_query("Grupo Niche"),
                "https://www.youtube.com/watch?v=YmQiUg75q84",
            )
            self.assertEqual(
                _resolve_youtube_query("Persiana Americana"),
                "Persiana Americana audio oficial",
            )
        finally:
            music_module.MUSIC_CACHE = previous

    def test_reuses_configured_alias_from_disk_after_restart(self):
        from plugins_func.functions import play_music as music_module

        previous = music_module.MUSIC_CACHE
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                cache_dir = Path(temp_dir)
                expected_path = cache_dir / "YmQiUg75q84.mp3"
                expected_path.write_bytes(b"cached audio")
                conn = SimpleNamespace(
                    config={
                        "plugins": {
                            "play_music": {
                                "music_dir": str(cache_dir / "music"),
                                "youtube_cache_dir": str(cache_dir),
                                "youtube_aliases": {
                                    "grupo niche": {
                                        "url": "https://www.youtube.com/watch?v=YmQiUg75q84",
                                        "title": "Grupo Niche - Nuestro Sueño",
                                    }
                                },
                            }
                        }
                    }
                )
                music_module.MUSIC_CACHE = {}
                initialize_music_handler(conn)

                cached = _cached_youtube_result(
                    "https://www.youtube.com/watch?v=YmQiUg75q84"
                )
                self.assertEqual(cached, (expected_path, "Grupo Niche - Nuestro Sueño"))
        finally:
            music_module.MUSIC_CACHE = previous


if __name__ == "__main__":
    unittest.main()
