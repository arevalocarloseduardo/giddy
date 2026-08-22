import os
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[2]
NATIVE_DIR = SERVER_DIR / "native"
FFMPEG_EXE = NATIVE_DIR / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
FFPROBE_EXE = NATIVE_DIR / ("ffprobe.exe" if os.name == "nt" else "ffprobe")


def configure_media_tools():
    if FFMPEG_EXE.is_file():
        current_path = os.environ.get("PATH", "")
        native_path = str(NATIVE_DIR)
        if native_path.lower() not in current_path.lower().split(os.pathsep):
            os.environ["PATH"] = native_path + os.pathsep + current_path
        return str(FFMPEG_EXE)
    return "ffmpeg"
