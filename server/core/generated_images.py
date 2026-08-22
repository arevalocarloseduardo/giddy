import json
import os
import re
import shutil
import subprocess
import threading
import urllib.request
import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlparse

from PIL import Image, ImageOps


SERVER_DIR = Path(__file__).resolve().parents[1]
GENERATED_IMAGE_DIR = SERVER_DIR / "data" / "giddy-generated-images"
IMAGE_GENERATION_LOCK = threading.Lock()
HERMES_IMAGE_SCRIPT = """
import json
import sys
from tools.image_generation_tool import _handle_image_generate

arguments = json.load(sys.stdin)
print(_handle_image_generate(arguments, task_id="giddy-voice"))
""".strip()


class GeneratedImageError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedImage:
    original_path: Path
    preview_path: Path
    prompt: str


def _parse_json_output(stdout: str):
    value = str(stdout or "").strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(value):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(value[index:])
                return payload
            except json.JSONDecodeError:
                continue
    raise GeneratedImageError("Hermes no devolvio un resultado de imagen valido")


def _run_hermes_generator(config: dict, prompt: str, aspect_ratio: str):
    plugin = config.get("plugins", {}).get("generate_image", {})
    container = str(plugin.get("docker_container", "hermes-giddy")).strip()
    timeout = max(30, int(plugin.get("timeout_seconds", 120)))
    docker = shutil.which(str(plugin.get("docker_command", "docker")))
    if not docker:
        raise GeneratedImageError("Docker no esta disponible para generar la imagen")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", container):
        raise GeneratedImageError("El contenedor de imagenes configurado no es valido")

    command = [
        docker,
        "exec",
        "-i",
        "-w",
        "/opt/hermes",
        container,
        "/opt/hermes/.venv/bin/python",
        "-c",
        HERMES_IMAGE_SCRIPT,
    ]
    try:
        with IMAGE_GENERATION_LOCK:
            result = subprocess.run(
                command,
                input=json.dumps({"prompt": prompt, "aspect_ratio": aspect_ratio}),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except subprocess.TimeoutExpired as exc:
        raise GeneratedImageError("Grok demoro demasiado en crear la imagen") from exc
    except OSError as exc:
        raise GeneratedImageError("No pude iniciar el generador de imagenes") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        message = detail[-1][:240] if detail else "error desconocido"
        raise GeneratedImageError(f"Grok no pudo crear la imagen: {message}")

    payload = _parse_json_output(result.stdout)
    if not isinstance(payload, dict) or not payload.get("success") or not payload.get("image"):
        message = str(payload.get("error") or "el generador no devolvio una imagen")
        raise GeneratedImageError(message[:300])
    return str(payload["image"]), container


def _safe_extension(value: str) -> str:
    extension = Path(urlparse(value).path).suffix.casefold()
    return extension if extension in {".png", ".jpg", ".jpeg", ".webp"} else ".png"


def _copy_generated_source(source: str, container: str, destination: Path, max_bytes: int):
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        request = urllib.request.Request(source, headers={"User-Agent": "Giddy/2.4"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response, destination.open("wb") as output:
                total = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise GeneratedImageError("La imagen generada es demasiado pesada")
                    output.write(chunk)
        except GeneratedImageError:
            raise
        except Exception as exc:
            raise GeneratedImageError("No pude guardar la imagen generada") from exc
        return

    source_path = source.replace("\\", "/")
    if not source_path.startswith(("/opt/data/", "/root/.hermes/")):
        raise GeneratedImageError("Hermes devolvio una ruta de imagen no permitida")
    docker = shutil.which("docker")
    if not docker:
        raise GeneratedImageError("Docker no esta disponible para recuperar la imagen")
    result = subprocess.run(
        [docker, "cp", f"{container}:{source_path}", str(destination)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or not destination.is_file():
        raise GeneratedImageError("No pude recuperar la imagen creada por Hermes")
    if destination.stat().st_size > max_bytes:
        destination.unlink(missing_ok=True)
        raise GeneratedImageError("La imagen generada es demasiado pesada")


def _ollama_request(base_url: str, payload: dict, timeout: int = 20):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def _warm_ollama_later(base_url: str, model: str, keep_alive: str):
    if not base_url or not model:
        return

    def warm():
        try:
            _ollama_request(
                base_url,
                {
                    "model": model,
                    "prompt": "hola",
                    "stream": False,
                    "keep_alive": keep_alive,
                    "options": {"num_predict": 1},
                },
                timeout=90,
            )
        except Exception:
            pass

    threading.Thread(target=warm, name="giddy-ollama-warm", daemon=True).start()


def _run_local_generator(
    config: dict,
    prompt: str,
    aspect_ratio: str,
    destination: Path,
):
    plugin = config.get("plugins", {}).get("generate_image", {})
    docker = shutil.which(str(plugin.get("docker_command", "docker")))
    if not docker:
        raise GeneratedImageError("Docker no esta disponible para el generador local")

    image = str(plugin.get("local_docker_image", "giddy-image-local:latest")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_./:-]+", image):
        raise GeneratedImageError("La imagen Docker del generador local no es valida")
    timeout = max(60, int(plugin.get("local_timeout_seconds", 300)))
    ollama_url = str(plugin.get("local_ollama_url", "http://127.0.0.1:11434")).strip()
    ollama_model = str(plugin.get("local_ollama_model", "qwen3.5:9b")).strip()
    ollama_keep_alive = str(plugin.get("local_ollama_keep_alive", "2h")).strip()

    try:
        if ollama_url and ollama_model:
            _ollama_request(
                ollama_url,
                {"model": ollama_model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=20,
            )
    except Exception:
        pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    container_name = f"giddy-image-{uuid.uuid4().hex[:10]}"
    command = [
        docker,
        "run",
        "--rm",
        "--gpus",
        "all",
        "--name",
        container_name,
        "-i",
        "-v",
        f"{destination.parent.resolve()}:/output",
        "-v",
        "giddy-image-models:/root/.cache/huggingface",
        image,
    ]
    request = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output": destination.name,
    }
    try:
        with IMAGE_GENERATION_LOCK:
            result = subprocess.run(
                command,
                input=json.dumps(request),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except subprocess.TimeoutExpired as exc:
        raise GeneratedImageError("El generador local demoro demasiado") from exc
    except OSError as exc:
        raise GeneratedImageError("No pude iniciar el generador local") from exc
    finally:
        _warm_ollama_later(ollama_url, ollama_model, ollama_keep_alive)

    if result.returncode != 0 or not destination.is_file():
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        message = " | ".join(detail[-4:])[-600:] if detail else "el contenedor no devolvio una imagen"
        raise GeneratedImageError(f"El generador local fallo: {message}")


def _create_preview(original_path: Path, preview_path: Path, size: int, _quality: int):
    try:
        with Image.open(original_path) as source:
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            fitted = ImageOps.contain(
                image,
                (size, size),
                method=Image.Resampling.LANCZOS,
            )
            canvas = Image.new("RGB", (size, size), "black")
            offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
            canvas.paste(fitted, offset)
            # Giddy's firmware ships with LVGL's PNG decoder. JPEG previews were
            # valid files but the device could not identify them at runtime.
            canvas.save(preview_path, format="PNG", optimize=True, compress_level=6)
    except Exception as exc:
        raise GeneratedImageError("El archivo generado no es una imagen valida") from exc


def _prune_generated_images(max_generations: int):
    files = sorted(
        (path for path in GENERATED_IMAGE_DIR.iterdir() if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    protected_files = max(2, max_generations * 2)
    for path in files[protected_files:]:
        path.unlink(missing_ok=True)


def generate_image_asset(config: dict, prompt: str, aspect_ratio: str) -> GeneratedImage:
    plugin = config.get("plugins", {}).get("generate_image", {})
    max_bytes = max(1, int(plugin.get("max_image_mb", 12))) * 1024 * 1024
    preview_size = max(160, min(240, int(plugin.get("preview_size", 240))))
    preview_quality = max(60, min(95, int(plugin.get("preview_quality", 88))))
    max_generations = max(2, int(plugin.get("cache_generations", 12)))

    GENERATED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_id = uuid.uuid4().hex
    preview_path = GENERATED_IMAGE_DIR / f"{image_id}-preview.png"
    try:
        try:
            source, container = _run_hermes_generator(config, prompt, aspect_ratio)
            original_path = GENERATED_IMAGE_DIR / f"{image_id}-original{_safe_extension(source)}"
            _copy_generated_source(source, container, original_path, max_bytes)
        except GeneratedImageError:
            if not bool(plugin.get("local_fallback_enabled", True)):
                raise
            original_path = GENERATED_IMAGE_DIR / f"{image_id}-original.png"
            _run_local_generator(config, prompt, aspect_ratio, original_path)
            if original_path.stat().st_size > max_bytes:
                raise GeneratedImageError("La imagen local generada es demasiado pesada")
        _create_preview(original_path, preview_path, preview_size, preview_quality)
    except Exception:
        if "original_path" in locals():
            original_path.unlink(missing_ok=True)
        preview_path.unlink(missing_ok=True)
        raise
    _prune_generated_images(max_generations)
    return GeneratedImage(original_path=original_path, preview_path=preview_path, prompt=prompt)


def generated_image_url(config: dict, path: Path) -> str:
    if path.parent.resolve() != GENERATED_IMAGE_DIR.resolve():
        raise GeneratedImageError("La vista previa no pertenece al almacen de imagenes")
    plugin = config.get("plugins", {}).get("generate_image", {})
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
    return f"{base}/giddy/generated/{quote(path.name)}"


def resolve_generated_image(filename: str):
    safe_name = Path(str(filename or "")).name
    if safe_name != filename or not re.fullmatch(
        r"[0-9a-f]{32}-(?:original\.(?:png|jpe?g|webp)|preview\.(?:png|jpg))",
        safe_name,
    ):
        return None
    path = GENERATED_IMAGE_DIR / safe_name
    return path if path.is_file() else None
