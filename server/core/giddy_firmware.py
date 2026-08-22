import asyncio
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from config.logger import setup_logging
from core.providers.tools.device_mcp import call_mcp_tool


SERVER_DIR = Path(__file__).resolve().parents[1]
GIDDY_FIRMWARE_DIR = SERVER_DIR / "data" / "giddy-firmware"
GIDDY_ASSET_STATE = SERVER_DIR / "data" / "giddy-assets-state.json"
STATE_LOCK = threading.Lock()
logger = setup_logging()
TAG = __name__


def resolve_giddy_firmware(filename: str):
    safe_name = Path(str(filename or "")).name
    if safe_name != filename or not re.fullmatch(
        r"giddy-assets-[A-Za-z0-9._-]+\.bin",
        safe_name,
    ):
        return None
    path = GIDDY_FIRMWARE_DIR / safe_name
    return path if path.is_file() else None


def giddy_asset_url(config: dict, filename: str) -> str:
    plugin = config.get("plugins", {}).get("giddy_assets", {})
    configured_base = str(plugin.get("public_base_url", "")).strip().rstrip("/")
    if configured_base:
        base = configured_base
    else:
        server = config.get("server", {})
        vision_url = urlparse(str(server.get("vision_explain", "")))
        if vision_url.scheme in {"http", "https"} and vision_url.netloc:
            base = f"{vision_url.scheme}://{vision_url.netloc}"
        else:
            websocket_url = urlparse(str(server.get("websocket", "")))
            host = websocket_url.hostname or "127.0.0.1"
            port = int(server.get("http_port", 8003))
            base = f"http://{host}:{port}"
    return f"{base}/giddy/firmware/{quote(filename)}"


def _load_state():
    try:
        value = json.loads(GIDDY_ASSET_STATE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _is_deployed(device_id: str, version: str) -> bool:
    with STATE_LOCK:
        entry = _load_state().get(device_id)
        if isinstance(entry, str):
            return entry == version
        return isinstance(entry, dict) and entry.get("version") == version and entry.get(
            "status"
        ) == "confirmed"


def _state_entry(device_id: str):
    with STATE_LOCK:
        entry = _load_state().get(device_id)
    if isinstance(entry, str):
        return {"version": entry, "status": "confirmed", "attempts": 1}
    return entry if isinstance(entry, dict) else {}


def _mark_state(device_id: str, version: str, status: str, **details):
    with STATE_LOCK:
        state = _load_state()
        previous = state.get(device_id)
        attempts = previous.get("attempts", 0) if isinstance(previous, dict) else 0
        state[device_id] = {
            "version": version,
            "status": status,
            "attempts": int(details.pop("attempts", attempts)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        GIDDY_ASSET_STATE.parent.mkdir(parents=True, exist_ok=True)
        temporary = GIDDY_ASSET_STATE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(GIDDY_ASSET_STATE)


def record_giddy_assets_hello(conn, msg_json: dict):
    """Confirm an asset deployment from capabilities reported after reboot."""
    config = getattr(conn, "config", {})
    plugin = config.get("plugins", {}).get("giddy_assets", {})
    if not bool(plugin.get("enabled", False)):
        return None
    version = str(plugin.get("version", "")).strip()
    device_id = str(getattr(conn, "device_id", "") or "").strip().casefold()
    entry = _state_entry(device_id)
    if not device_id or entry.get("version") != version or entry.get("status") != "pending":
        return None

    expected_charset = str(plugin.get("expected_charset", "common")).strip().casefold()
    text_font = msg_json.get("text_font")
    observed_charset = (
        str(text_font.get("charset", "")).strip().casefold()
        if isinstance(text_font, dict)
        else ""
    )
    confirmed = observed_charset == expected_charset
    status = "confirmed" if confirmed else "failed"
    _mark_state(
        device_id,
        version,
        status,
        attempts=entry.get("attempts", 0),
        observed_charset=observed_charset or "missing",
    )
    log = logger.bind(tag=TAG)
    if confirmed:
        log.info(f"Assets Giddy {version} confirmados por {device_id}")
    else:
        log.warning(
            f"Assets Giddy {version} rechazados por {device_id}: "
            f"charset={observed_charset or 'missing'}"
        )
    return confirmed


async def deploy_pending_giddy_assets(conn, mcp_client):
    plugin = conn.config.get("plugins", {}).get("giddy_assets", {})
    if not bool(plugin.get("enabled", False)):
        return False
    # OTA is the single automatic delivery path. MCP remains available only as
    # an explicit fallback so the same package can never schedule two reboots.
    if str(plugin.get("delivery", "ota")).strip().casefold() != "mcp":
        return False
    version = str(plugin.get("version", "")).strip()
    filename = str(plugin.get("filename", "")).strip()
    device_id = str(getattr(conn, "device_id", "") or "").strip().casefold()
    if not device_id:
        return False
    if not version or not resolve_giddy_firmware(filename):
        return False
    if _is_deployed(device_id, version):
        return False
    entry = _state_entry(device_id)
    if entry.get("version") == version and entry.get("status") == "pending":
        return False
    attempts = int(entry.get("attempts", 0)) if entry.get("version") == version else 0
    max_attempts = max(1, int(plugin.get("max_attempts", 3)))
    if attempts >= max_attempts:
        logger.bind(tag=TAG).error(
            f"Assets Giddy {version} agotaron {max_attempts} intentos para {device_id}"
        )
        return False
    if not mcp_client.has_tool("self_assets_set_download_url"):
        logger.bind(tag=TAG).warning("El dispositivo no permite actualizar sus assets por MCP")
        return False

    await asyncio.sleep(0.5)
    url = giddy_asset_url(conn.config, filename)
    attempts += 1
    try:
        result = await call_mcp_tool(
            conn,
            mcp_client,
            "self.assets.set_download_url",
            {"url": url},
            timeout=15,
        )
        if str(result).strip().casefold() in {"false", "null", "none", "0"}:
            raise RuntimeError(f"El dispositivo rechazo la URL de assets: {result}")
    except Exception:
        _mark_state(device_id, version, "failed", attempts=attempts)
        raise
    _mark_state(device_id, version, "pending", attempts=attempts)
    logger.bind(tag=TAG).info(
        f"Assets Giddy {version} enviados a {device_id}; esperando confirmacion tras reinicio"
    )
    if mcp_client.has_tool("self_reboot"):
        try:
            await call_mcp_tool(conn, mcp_client, "self.reboot", {}, timeout=8)
        except (TimeoutError, ConnectionError):
            # A successful reboot normally closes the socket before its MCP
            # response can arrive. The next hello is the real confirmation.
            logger.bind(tag=TAG).info(
                f"{device_id} se desconecto para reiniciar; esperando nuevo hello"
            )
    else:
        await conn.websocket.send(json.dumps({"type": "system", "command": "reboot"}))
    return True


async def deploy_pending_giddy_assets_safely(conn, mcp_client):
    try:
        return await deploy_pending_giddy_assets(conn, mcp_client)
    except Exception as exc:
        logger.bind(tag=TAG).warning(
            f"No se pudo programar la actualizacion de assets de Giddy: {exc}"
        )
        return False
