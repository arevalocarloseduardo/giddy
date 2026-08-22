import asyncio
import time

from core.generated_images import (
    GeneratedImageError,
    generate_image_asset,
    generated_image_url,
)
from core.providers.tools.device_mcp import call_mcp_tool
from core.providers.tts.dto.dto import ContentType, SentenceType, TTSMessageDTO
from core.interaction_guard import begin_exclusive_operation, end_exclusive_operation
from plugins_func.register import Action, ActionResponse, ToolType, register_function


generate_image_function_desc = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "Crea una imagen con Grok Imagine, la guarda y la muestra en la pantalla "
            "de Giddy. Usala siempre que el usuario pida crear una imagen, foto, "
            "ilustracion, flyer, afiche o dibujo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Descripcion clara de la imagen que se debe crear.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["square", "portrait", "landscape"],
                    "description": "Formato cuadrado, vertical u horizontal.",
                },
            },
            "required": ["prompt"],
        },
    },
}


def _queue_message(conn, sentence_type, content_type, text=None):
    conn.tts.tts_text_queue.put(
        TTSMessageDTO(
            sentence_id=conn.sentence_id,
            sentence_type=sentence_type,
            content_type=content_type,
            content_detail=text,
        )
    )


def _open_response(conn, text: str):
    _queue_message(conn, SentenceType.FIRST, ContentType.ACTION)
    conn.tts.store_tts_text(conn.sentence_id, text)
    _queue_message(conn, SentenceType.MIDDLE, ContentType.TEXT, text)


def _close_response(conn, text: str):
    conn.tts.store_tts_text(conn.sentence_id, text)
    _queue_message(conn, SentenceType.MIDDLE, ContentType.TEXT, text)
    _queue_message(conn, SentenceType.LAST, ContentType.ACTION)


async def _show_on_device(conn, url: str):
    mcp_client = getattr(conn, "mcp_client", None)
    if mcp_client is None:
        raise GeneratedImageError("La pantalla del dispositivo no esta conectada")
    await call_mcp_tool(
        conn,
        mcp_client,
        "self.screen.preview_image",
        {"url": url},
        timeout=25,
    )


@register_function("generate_image", generate_image_function_desc, ToolType.SYSTEM_CTL)
async def generate_image(conn, prompt: str, aspect_ratio: str = "square"):
    begin_exclusive_operation(conn, "generate_image")
    try:
        prompt = str(prompt or "").strip()
        if len(prompt) < 2:
            conn.giddy_pending_image_until = time.monotonic() + 60.0
            return ActionResponse(
                action=Action.RESPONSE,
                result="Falta describir la imagen",
                response="Decime que imagen queres que cree.",
            )
        conn.giddy_pending_image_until = 0.0
        if aspect_ratio not in {"square", "portrait", "landscape"}:
            aspect_ratio = "square"

        conn.tts_emotion = {
            "sentence_id": conn.sentence_id,
            "emotion": "painting",
        }
        _open_response(conn, "La estoy creando.")
        asset = await asyncio.to_thread(
            generate_image_asset,
            conn.config,
            prompt[:1800],
            aspect_ratio,
        )
        preview_url = generated_image_url(conn.config, asset.preview_path)
        await _show_on_device(conn, preview_url)
        _close_response(conn, "Listo, te la muestro.")
        return ActionResponse(
            action=Action.RECORD,
            result=f"Imagen generada y mostrada: {asset.original_path}",
            response=None,
        )
    except Exception as exc:
        _close_response(conn, "No pude crear o mostrar la imagen esta vez.")
        message = str(exc) if isinstance(exc, GeneratedImageError) else "Fallo la generacion de imagen"
        return ActionResponse(
            action=Action.RECORD,
            result=message,
            response=None,
        )
    finally:
        end_exclusive_operation(conn, "generate_image")
