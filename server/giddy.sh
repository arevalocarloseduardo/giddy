#!/bin/bash
# Control del servidor local de Giddy (xiaozhi-esp32-server)
# Uso: ./giddy.sh start|stop|status|log

DIR="$(cd "$(dirname "$0")/main/xiaozhi-server" && pwd)"
LOG="$DIR/data/server.log"
LABEL="com.charli.giddy-server"

pid() {
  launchctl list "$LABEL" 2>/dev/null |
    awk '/"PID"/ { gsub(/;/, "", $3); print $3; exit }'
}

wait_until_removed() {
  for _ in {1..50}; do
    launchctl list "$LABEL" >/dev/null 2>&1 || return 0
    sleep 0.1
  done
  return 1
}

case "$1" in
  start)
    if [ -n "$(pid)" ]; then echo "Ya está corriendo (PID $(pid))"; exit 0; fi
    launchctl remove "$LABEL" >/dev/null 2>&1
    wait_until_removed || {
      echo "No se pudo limpiar el servicio anterior de Giddy"
      exit 1
    }
    # ollama como servicio (solo necesario si el LLM es OllamaLLM, no molesta tenerlo)
    curl -s http://localhost:11434/api/tags >/dev/null || brew services start ollama
    launchctl submit -l "$LABEL" -o "$LOG" -e "$LOG" -- \
      /bin/zsh -lc "cd \"$DIR\" && exec ./venv/bin/python app.py"
    sleep 1
    if [ -n "$(pid)" ]; then
      echo "Giddy server arrancando (PID $(pid)) — log: $LOG"
    else
      echo "No se pudo iniciar Giddy. Revisá el log: $LOG"
      exit 1
    fi
    ;;
  stop)
    p="$(pid)"
    if [ -n "$p" ]; then
      launchctl remove "$LABEL"
      wait_until_removed
      echo "Detenido (PID $p)"
    else
      launchctl remove "$LABEL" >/dev/null 2>&1
      wait_until_removed
      echo "No estaba corriendo"
    fi
    ;;
  status)
    if [ -n "$(pid)" ]; then
      echo "CORRIENDO (PID $(pid))"
      echo "OTA:       http://192.168.0.51:8003/xiaozhi/ota/"
      echo "WebSocket: ws://192.168.0.51:8000/xiaozhi/v1/"
      grep -m1 "LLM" "$DIR/data/.config.yaml" >/dev/null && grep "model_name" "$DIR/data/.config.yaml" | head -1
    else
      echo "DETENIDO"
    fi
    ;;
  log)
    tail -40 "$LOG"
    ;;
  *)
    echo "Uso: $0 start|stop|status|log"
    ;;
esac
