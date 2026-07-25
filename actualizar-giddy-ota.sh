#!/bin/zsh
set -eo pipefail

HARDWARE_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="${0:A}"
FIRMWARE_DIR="$HARDWARE_DIR/xiaozhi-esp32"
SERVER_DIR="$HARDWARE_DIR/xiaozhi-esp32-server"
CMAKE_FILE="$FIRMWARE_DIR/CMakeLists.txt"
APP_BINARY="$FIRMWARE_DIR/build/xiaozhi.bin"
OTA_DIR="$SERVER_DIR/main/xiaozhi-server/data/bin"
BOARD_MODEL="esp32-s3-touch-lcd-1.54"
IDF_EXPORT="/Users/mac/esp/esp-idf/export.sh"
IDF_PYTHON_ENV="/Users/mac/.espressif/python_env/idf6.0_py3.12_env"

usage() {
  echo "Uso: $SCRIPT_PATH [VERSION]"
  echo "     $SCRIPT_PATH --check"
  echo
  echo "Sin VERSION aumenta automáticamente el último número."
  echo "Ejemplo: 2.4.0 pasa a 2.4.1."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
  shift
fi

if [[ ! -f "$CMAKE_FILE" || ! -f "$IDF_EXPORT" ]]; then
  echo "No se encontró el proyecto o ESP-IDF."
  exit 1
fi

if ! rg -q '^CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54=y$' \
  "$FIRMWARE_DIR/sdkconfig"; then
  echo "La configuración activa no corresponde a la pantalla Waveshare 1.54."
  exit 1
fi

CURRENT_VERSION="$(
  sed -nE 's/^set\(PROJECT_VER "([^"]+)"\)$/\1/p' "$CMAKE_FILE" | head -1
)"
if [[ -z "$CURRENT_VERSION" ]]; then
  echo "No se pudo leer PROJECT_VER en $CMAKE_FILE."
  exit 1
fi

if [[ -n "${1:-}" ]]; then
  NEXT_VERSION="$1"
else
  NEXT_VERSION="$(
    python3 - "$CURRENT_VERSION" <<'PY'
import re
import sys

match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", sys.argv[1])
if not match:
    raise SystemExit("La versión actual no tiene formato X.Y.Z")
major, minor, patch = map(int, match.groups())
print(f"{major}.{minor}.{patch + 1}")
PY
  )"
fi

python3 - "$CURRENT_VERSION" "$NEXT_VERSION" <<'PY'
import re
import sys

current, requested = sys.argv[1:3]
pattern = re.compile(r"^\d+\.\d+\.\d+$")
if not pattern.fullmatch(requested):
    raise SystemExit("La nueva versión debe tener formato X.Y.Z")
if tuple(map(int, requested.split("."))) <= tuple(map(int, current.split("."))):
    raise SystemExit(f"La nueva versión ({requested}) debe ser mayor que {current}")
PY

OTA_BINARY="$OTA_DIR/${BOARD_MODEL}_${NEXT_VERSION}.bin"
if [[ -e "$OTA_BINARY" ]]; then
  echo "Ya existe una OTA con la versión $NEXT_VERSION: $OTA_BINARY"
  exit 1
fi

if $CHECK_ONLY; then
  echo "OTA lista para preparar: Giddy $CURRENT_VERSION -> $NEXT_VERSION"
  echo "Destino: $OTA_BINARY"
  echo "No se modificó ningún archivo."
  exit 0
fi

echo "Preparando Giddy $CURRENT_VERSION -> $NEXT_VERSION"

python3 - "$CMAKE_FILE" "$CURRENT_VERSION" "$NEXT_VERSION" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
current, requested = sys.argv[2:4]
text = path.read_text()
old = f'set(PROJECT_VER "{current}")'
new = f'set(PROJECT_VER "{requested}")'
if text.count(old) != 1:
    raise SystemExit("No se encontró una única declaración de PROJECT_VER")
path.write_text(text.replace(old, new, 1))
PY

export IDF_PYTHON_ENV_PATH="$IDF_PYTHON_ENV"
source "$IDF_EXPORT"

echo "Compilando firmware..."
idf.py -C "$FIRMWARE_DIR" build

if [[ ! -s "$APP_BINARY" ]]; then
  echo "La compilación terminó sin generar $APP_BINARY."
  exit 1
fi

mkdir -p "$OTA_DIR"
cp "$APP_BINARY" "$OTA_BINARY"

echo "Publicando OTA..."
"$SERVER_DIR/giddy.sh" stop >/dev/null
"$SERVER_DIR/giddy.sh" start

echo
echo "OTA Giddy $NEXT_VERSION lista:"
echo "  $OTA_BINARY"
echo "  $(shasum -a 256 "$OTA_BINARY" | awk '{print $1}')"
echo
echo "Dejá el dispositivo conectado a la corriente y a la misma red Wi-Fi."
echo "Reinicialo: descargará la actualización y volverá a arrancar solo."
