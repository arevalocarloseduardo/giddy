import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.generated_images import (
    GeneratedImageError,
    _create_preview,
    _parse_json_output,
    generate_image_asset,
    generated_image_url,
    resolve_generated_image,
)
from core.api.ota_handler import _giddy_assets_payload
from core.providers.tools.device_mcp import MCPClient, call_mcp_tool
from core.giddy_firmware import deploy_pending_giddy_assets, record_giddy_assets_hello
from core.providers.intent.giddy_intent.giddy_intent import IntentProvider
from core.utils.image_queries import parse_image_request
from plugins_func.functions.generate_image import generate_image


class GiddyImageIntentTests(unittest.IsolatedAsyncioTestCase):
    async def test_remembers_that_the_next_turn_describes_the_image(self):
        provider = IntentProvider({})
        conn = SimpleNamespace()

        first = json.loads(
            await provider.detect_intent(conn, [], "Si me puedes crear una imagen.")
        )
        second = json.loads(
            await provider.detect_intent(conn, [], "un perrito comiendo helado")
        )

        self.assertEqual(first["function_call"]["name"], "generate_image")
        self.assertEqual(first["function_call"]["arguments"]["prompt"], "")
        self.assertEqual(second["function_call"]["name"], "generate_image")
        self.assertEqual(
            second["function_call"]["arguments"],
            {"prompt": "un perrito comiendo helado", "aspect_ratio": "square"},
        )

    async def test_routes_image_creation_without_waiting_for_the_llm(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "Creame una imagen vertical de un robot tocando la guitarra",
            )
        )

        self.assertEqual(result["function_call"]["name"], "generate_image")
        self.assertEqual(
            result["function_call"]["arguments"],
            {
                "prompt": "un robot tocando la guitarra",
                "aspect_ratio": "portrait",
            },
        )

    async def test_routes_natural_show_me_image_request_from_live_asr(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(
                None,
                [],
                "Dame la imagen de un gatito con el nalado.",
            )
        )

        self.assertEqual(result["function_call"]["name"], "generate_image")
        self.assertEqual(
            result["function_call"]["arguments"],
            {
                "prompt": "un gatito con el nalado",
                "aspect_ratio": "square",
            },
        )

    async def test_does_not_treat_image_questions_as_generation(self):
        provider = IntentProvider({})
        result = json.loads(
            await provider.detect_intent(None, [], "Que es una imagen vectorial?")
        )
        self.assertEqual(result["function_call"]["name"], "continue_chat")


class GeneratedImageTests(unittest.IsolatedAsyncioTestCase):
    def test_detects_landscape_flyer_request(self):
        self.assertEqual(
            parse_image_request("Haceme un flyer horizontal con una peluqueria moderna"),
            ("una peluqueria moderna", "landscape"),
        )

    def test_parses_json_after_a_harmless_log_line(self):
        payload = _parse_json_output(
            'provider ready\n{"success": true, "image": "/opt/data/cache/a.png"}'
        )
        self.assertEqual(payload["image"], "/opt/data/cache/a.png")

    def test_creates_a_square_preview_without_stretching(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp_dir:
            original = Path(temp_dir) / "original.png"
            preview = Path(temp_dir) / "preview.png"
            Image.new("RGB", (80, 160), "red").save(original)

            _create_preview(original, preview, 240, 85)

            with Image.open(preview) as result:
                self.assertEqual(result.format, "PNG")
                self.assertEqual(result.size, (240, 240))
                self.assertLess(sum(result.getpixel((10, 120))), 30)
                self.assertGreater(result.getpixel((120, 120))[0], 180)

    def test_builds_a_device_reachable_preview_url(self):
        with patch("core.generated_images.GENERATED_IMAGE_DIR", Path("C:/tmp/images")):
            path = Path("C:/tmp/images/" + "a" * 32 + "-preview.png")
            url = generated_image_url(
                {
                    "server": {
                        "vision_explain": "http://192.168.0.10:8003/mcp/vision/explain"
                    }
                },
                path,
            )
        self.assertEqual(
            url,
            "http://192.168.0.10:8003/giddy/generated/"
            + "a" * 32
            + "-preview.png",
        )

    def test_public_store_accepts_png_previews(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)
            filename = "a" * 32 + "-preview.png"
            (image_dir / filename).write_bytes(b"\x89PNG\r\n\x1a\n")
            with patch("core.generated_images.GENERATED_IMAGE_DIR", image_dir):
                resolved = resolve_generated_image(filename)

        self.assertEqual(resolved.name, filename)

    async def test_image_generation_marks_the_painting_scene(self):
        import queue

        conn = SimpleNamespace(
            sentence_id="sentence-1",
            config={},
            giddy_pending_image_until=0.0,
            tts_emotion=None,
            tts=SimpleNamespace(
                tts_text_queue=queue.Queue(),
                store_tts_text=lambda *_args: None,
            ),
        )
        asset = SimpleNamespace(
            original_path=Path("original.png"),
            preview_path=Path("preview.png"),
        )
        with (
            patch(
                "plugins_func.functions.generate_image.generate_image_asset",
                return_value=asset,
            ),
            patch(
                "plugins_func.functions.generate_image.generated_image_url",
                return_value="http://device/preview.png",
            ),
            patch(
                "plugins_func.functions.generate_image._show_on_device",
                new=AsyncMock(),
            ),
        ):
            await generate_image(conn, "un robot pintando", "square")

        self.assertEqual(conn.tts_emotion["emotion"], "painting")
        self.assertIsNone(conn.giddy_exclusive_operation)
        self.assertGreater(conn.giddy_ignore_audio_until, time.monotonic())

    def test_uses_local_generator_when_remote_quota_is_unavailable(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp_dir:
            image_dir = Path(temp_dir)

            def create_local(_config, _prompt, _aspect_ratio, destination):
                Image.new("RGB", (320, 180), "cyan").save(destination)

            config = {
                "plugins": {
                    "generate_image": {
                        "local_fallback_enabled": True,
                        "preview_size": 240,
                    }
                }
            }
            with (
                patch("core.generated_images.GENERATED_IMAGE_DIR", image_dir),
                patch(
                    "core.generated_images._run_hermes_generator",
                    side_effect=GeneratedImageError("quota"),
                ),
                patch("core.generated_images._run_local_generator", side_effect=create_local),
            ):
                result = generate_image_asset(config, "un robot feliz", "landscape")

            self.assertTrue(result.original_path.is_file())
            self.assertTrue(result.preview_path.is_file())
            with Image.open(result.preview_path) as preview:
                self.assertEqual(preview.size, (240, 240))


class DeviceMCPNameTests(unittest.IsolatedAsyncioTestCase):
    async def test_ota_delivery_never_schedules_a_second_mcp_reboot(self):
        class FakeConnection:
            device_id = "AA:BB:CC"
            config = {
                "plugins": {
                    "giddy_assets": {
                        "enabled": True,
                        "delivery": "ota",
                        "version": "2.4.14",
                        "filename": "giddy-assets-2.4.14.bin",
                    }
                }
            }

        call = AsyncMock()
        with patch("core.giddy_firmware.call_mcp_tool", call):
            deployed = await deploy_pending_giddy_assets(FakeConnection(), MCPClient())

        self.assertFalse(deployed)
        call.assert_not_awaited()

    def test_ota_advertises_assets_for_recovery_without_mcp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            firmware_dir = Path(temp_dir)
            (firmware_dir / "giddy-assets-2.4.14.bin").write_bytes(b"assets")
            config = {
                "server": {
                    "vision_explain": "http://192.168.0.10:8003/mcp/vision/explain"
                },
                "plugins": {
                    "giddy_assets": {
                        "enabled": True,
                        "version": "2.4.14",
                        "filename": "giddy-assets-2.4.14.bin",
                    }
                },
            }
            with patch("core.giddy_firmware.GIDDY_FIRMWARE_DIR", firmware_dir):
                payload = _giddy_assets_payload(
                    config, "esp32-s3-touch-lcd-1.54", "28:84:85:91:c0:4c"
                )
                unrelated = _giddy_assets_payload(config, "other-board", "unrelated")

        self.assertEqual(payload["version"], "2.4.14")
        self.assertEqual(payload["expected_charset"], "common")
        self.assertIsNone(unrelated)
        self.assertEqual(
            payload["url"],
            "http://192.168.0.10:8003/giddy/firmware/giddy-assets-2.4.14.bin",
        )

    async def test_accepts_original_dotted_device_tool_name(self):
        class FakeWebSocket:
            def __init__(self):
                self.messages = []

            async def send(self, message):
                self.messages.append(json.loads(message))

        class FakeConnection:
            features = {"mcp": True}
            websocket = FakeWebSocket()

        client = MCPClient()
        await client.add_tool(
            {
                "name": "self.screen.preview_image",
                "description": "preview",
                "inputSchema": {"type": "object", "properties": {}},
            }
        )
        await client.set_ready(True)
        connection = FakeConnection()
        task = asyncio.create_task(
            call_mcp_tool(
                connection,
                client,
                "self.screen.preview_image",
                {"url": "http://example/image.jpg"},
            )
        )
        await asyncio.sleep(0)
        sent = connection.websocket.messages[-1]["payload"]
        self.assertEqual(sent["params"]["name"], "self.screen.preview_image")
        await client.resolve_call_result(sent["id"], {"content": [{"text": "true"}]})
        self.assertEqual(await task, "true")

    async def test_stages_asset_update_only_once_per_device_and_version(self):
        class FakeConnection:
            device_id = "AA:BB:CC"
            config = {
                "server": {
                    "vision_explain": "http://192.168.0.10:8003/mcp/vision/explain"
                },
                "plugins": {
                    "giddy_assets": {
                        "enabled": True,
                        "delivery": "mcp",
                        "version": "2.4.14",
                        "filename": "giddy-assets-2.4.14.bin",
                    }
                },
            }

        client = MCPClient()
        for name in ("self.assets.set_download_url", "self.reboot"):
            await client.add_tool(
                {
                    "name": name,
                    "description": name,
                    "inputSchema": {"type": "object", "properties": {}},
                }
            )
        await client.set_ready(True)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            firmware_dir = root / "firmware"
            firmware_dir.mkdir()
            (firmware_dir / "giddy-assets-2.4.14.bin").write_bytes(b"assets")
            call = AsyncMock(return_value="true")
            with (
                patch("core.giddy_firmware.GIDDY_FIRMWARE_DIR", firmware_dir),
                patch("core.giddy_firmware.GIDDY_ASSET_STATE", root / "state.json"),
                patch("core.giddy_firmware.call_mcp_tool", call),
                patch("core.giddy_firmware.asyncio.sleep", AsyncMock()),
            ):
                first = await deploy_pending_giddy_assets(FakeConnection(), client)
                second = await deploy_pending_giddy_assets(FakeConnection(), client)
                pending = json.loads((root / "state.json").read_text(encoding="utf-8"))
                confirmed = record_giddy_assets_hello(
                    FakeConnection(), {"text_font": {"charset": "common"}}
                )
                final = json.loads((root / "state.json").read_text(encoding="utf-8"))

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(pending["aa:bb:cc"]["status"], "pending")
        self.assertTrue(confirmed)
        self.assertEqual(final["aa:bb:cc"]["status"], "confirmed")
        self.assertEqual(call.await_count, 2)
        self.assertEqual(call.await_args_list[0].args[2], "self.assets.set_download_url")
        self.assertEqual(
            call.await_args_list[0].args[3]["url"],
            "http://192.168.0.10:8003/giddy/firmware/giddy-assets-2.4.14.bin",
        )


if __name__ == "__main__":
    unittest.main()
