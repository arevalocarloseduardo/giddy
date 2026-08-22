import ctypes.util
import os
import sys
from pathlib import Path


def _find_opus():
    configured = os.environ.get("OPUS_DLL")
    candidates = [
        Path(configured) if configured else None,
        Path(sys.executable).resolve().parent / "opus.dll",
        Path(__file__).resolve().parents[2] / "native" / "opus.dll",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Wireshark" / "opus.dll",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return str(candidate)
    return None


_original_find_library = ctypes.util.find_library
_opus_path = _original_find_library("opus") or _find_opus()
if _opus_path:
    ctypes.util.find_library = lambda name: _opus_path if name == "opus" else _original_find_library(name)

try:
    import opuslib_next as opuslib_next
finally:
    ctypes.util.find_library = _original_find_library

