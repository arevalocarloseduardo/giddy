import asyncio
import secrets
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import edge_tts
from aiohttp import web

from core.generated_images import resolve_generated_image
from core.giddy_firmware import resolve_giddy_firmware
from core.product_settings import ALLOWED_VOICES, ProductSettings
from core.providers.llm.hybrid.hybrid import GiddyRouter
from core.providers.llm.hybrid.reflex import ReflexEngine


class GiddyPortal:
    def __init__(self, config, device_controller=None):
        selected = config.get("selected_module", {}).get("LLM", "")
        llm_config = config.get("LLM", {}).get(selected, {})
        self.settings = ProductSettings(llm_config.get("settings_path"))
        self.token = self.settings.setup_token()
        self.router = GiddyRouter()
        self.reflex = ReflexEngine()
        self.html_path = Path(__file__).resolve().parent / "web" / "giddy.html"
        self.server = config.get("server", {})
        self.device_controller = device_controller

    def routes(self):
        return [
            web.get("/giddy", self.index),
            web.get("/giddy/", self.index),
            web.get("/giddy/api/status", self.status),
            web.get("/giddy/api/config", self.get_config),
            web.post("/giddy/api/config", self.update_config),
            web.post("/giddy/api/route-preview", self.route_preview),
            web.post("/giddy/api/voice-preview", self.voice_preview),
            web.post("/giddy/api/device/reboot", self.reboot_device),
            web.get("/giddy/generated/{filename}", self.generated_image),
            web.get("/giddy/firmware/{filename}", self.firmware_asset),
        ]

    async def index(self, request):
        return web.FileResponse(self.html_path, headers={"Cache-Control": "no-store"})

    async def generated_image(self, request):
        path = resolve_generated_image(request.match_info.get("filename", ""))
        if path is None:
            raise web.HTTPNotFound(text="Imagen no encontrada")
        return web.FileResponse(
            path,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    async def firmware_asset(self, request):
        path = resolve_giddy_firmware(request.match_info.get("filename", ""))
        if path is None:
            raise web.HTTPNotFound(text="Paquete de firmware no encontrado")
        return web.FileResponse(path, headers={"Cache-Control": "no-store"})

    async def status(self, request):
        self._require_auth(request)
        settings = self.settings.load()
        routing = settings["routing"]
        targets = {
            "local": routing["local_url"].rstrip("/") + "/api/version",
            "hermes": "http://127.0.0.1:8664/health",
            "speech": "http://127.0.0.1:9000/health",
        }
        checks = await asyncio.gather(
            *(self._probe(name, url) for name, url in targets.items()),
            return_exceptions=True,
        )
        services = {name: False for name in targets}
        for result in checks:
            if isinstance(result, tuple):
                services[result[0]] = result[1]
        services["giddy"] = True
        return web.json_response({
            "ok": True,
            "services": services,
            "metrics": self.settings.metrics_summary(),
            "mode": settings["mode"],
            "assistant_name": settings["assistant_name"],
            "endpoints": {
                "websocket": self.server.get("websocket", ""),
                "ota": "/xiaozhi/ota/",
            },
        })

    async def get_config(self, request):
        self._require_auth(request)
        return web.json_response(self.settings.load())

    async def update_config(self, request):
        self._require_auth(request)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(text="Configuracion invalida")
        return web.json_response(self.settings.save(payload))

    async def route_preview(self, request):
        self._require_auth(request)
        payload = await request.json()
        text = str(payload.get("text", ""))[:1000]
        current = self.settings.load()
        reflex = self.reflex.match(text, current)
        if reflex:
            return web.json_response({"route": "instant", "reason": reflex.reason})
        mode = current["mode"]
        decision = self.router.choose(text, mode)
        return web.json_response({"route": decision.route, "reason": decision.reason})

    async def voice_preview(self, request):
        self._require_auth(request)
        payload = await request.json()
        text = str(payload.get("text", "Hola, soy Giddy. Estoy listo para ayudarte.")).strip()[:180]
        settings = self.settings.load()["voice"]
        voice = str(payload.get("voice", settings["voice"]))
        if voice not in ALLOWED_VOICES:
            voice = settings["voice"]
        try:
            rate_value = max(-10, min(40, int(payload.get("rate", settings["rate"]))))
            pitch_value = max(-50, min(50, int(payload.get("pitch", settings["pitch"]))))
            communicate = edge_tts.Communicate(
                text,
                voice=voice,
                rate=f"{rate_value:+}%",
                pitch=f"{pitch_value:+}Hz",
            )
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    audio.extend(chunk["data"])
            return web.Response(body=bytes(audio), content_type="audio/mpeg")
        except Exception as exc:
            raise web.HTTPServiceUnavailable(text=f"No se pudo probar la voz: {exc}")

    async def reboot_device(self, request):
        self._require_auth(request)
        if self.device_controller is None:
            raise web.HTTPServiceUnavailable(text="Control del dispositivo no disponible")
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        device_id = str(payload.get("device_id", "")).strip()
        result = await self.device_controller.send_system_command("reboot", device_id)
        if not result["delivered"]:
            raise web.HTTPConflict(
                text="No hay un dispositivo conectado con ese identificador"
            )
        return web.json_response({"ok": True, **result})

    async def _probe(self, name, url):
        timeout = aiohttp.ClientTimeout(total=1.5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    return name, response.status < 500
        except Exception:
            parsed = urlparse(url)
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(parsed.hostname, parsed.port),
                    timeout=1,
                )
                writer.close()
                await writer.wait_closed()
                return name, True
            except Exception:
                return name, False

    def _require_auth(self, request):
        header = request.headers.get("Authorization", "")
        supplied = header[7:] if header.startswith("Bearer ") else request.headers.get("X-Giddy-Token", "")
        if not supplied or not secrets.compare_digest(supplied, self.token):
            raise web.HTTPUnauthorized(text="Token de configuracion requerido")
