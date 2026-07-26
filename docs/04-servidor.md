# 04 — El servidor de Giddy

Base: [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) **v0.9.6** (despliegue mínimo Python, sin el panel Java) + nuestros parches.

> 🔒 **La versión está pineada a propósito.** El parche de `patches/` está hecho contra el tag **`v0.9.6`** (commit `f5ed1aa`). Si clonás la rama `main` en vez del tag, el upstream ya habrá cambiado y `git apply` puede fallar. Ver [docs/07-versiones.md](07-versiones.md).

## Paso 1 — Clonar, parchear, instalar

```bash
git clone --depth 1 -b v0.9.6 https://github.com/xinnan-tech/xiaozhi-esp32-server.git
cd xiaozhi-esp32-server
git apply ../patches/xiaozhi-esp32-server.patch
cd main/xiaozhi-server
python3.10 -m venv venv
```

> ⚠️ **El `requirements.txt` tiene un pin roto**: `vosk==0.3.45` no existe para mac arm64, y ese único pin aborta **todo** el pip install. Instalar así:

```bash
grep -v "^vosk" requirements.txt > /tmp/req.txt
./venv/bin/pip install -r /tmp/req.txt
./venv/bin/pip install vosk        # agarra la 0.3.44, que sí existe
```

## Paso 2 — La configuración (y las claves)

```bash
mkdir -p data
cp ../../../config/config.yaml.example data/.config.yaml
```

Ahora **editá `data/.config.yaml`** y reemplazá los placeholders con tus claves reales:

| Placeholder | Dónde sacar la clave | Costo |
|---|---|---|
| `sk-or-v1-TU_CLAVE_OPENROUTER_ACA` | [openrouter.ai](https://openrouter.ai) → Keys | ~US$0.35/mes |
| `gsk_TU_CLAVE_GROQ_ACA` | [console.groq.com](https://console.groq.com) → API Keys | **gratis** (free tier) |

También cambiá la IP en `server.websocket` y `server.vision_explain` por la de la máquina donde corre.

> 📌 `data/.config.yaml` **nunca** se commitea (está en el `.gitignore` del propio repo del servidor y en el nuestro). Sobreescribe a `config.yaml`; nunca edites `config.yaml` directo.

## Paso 3 — El modelo de voz en español (Vosk, opcional)

Solo si querés fallback offline del oído:

```bash
mkdir -p models/vosk && cd models/vosk
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
unzip vosk-model-small-es-0.42.zip && rm vosk-model-small-es-0.42.zip
```

## Paso 4 — Arrancar

```bash
./giddy.sh start     # también: stop | status | log
```

Debería loguear:

```
初始化组件: llm成功 OpenRouterLLM
初始化组件: asr成功 GroqASR
OTA接口是        http://TU_IP:8003/xiaozhi/ota/
Websocket地址是  ws://TU_IP:8000/xiaozhi/v1/
```

## El stack: qué hace cada pieza

| Etapa | Proveedor actual | Latencia | Costo |
|---|---|---|---|
| **VAD** (detectar que hablás) | SileroVAD (local) | — | gratis |
| 👂 **ASR** (audio → texto) | **Groq** `whisper-large-v3-turbo` | **0.44s** medido | gratis |
| 🧠 **LLM** (pensar) | **OpenRouter** `deepseek/deepseek-v3.2` | 1.7–2.3s medido | ~US$0.35/mes |
| 🗣️ **TTS** (texto → voz) | **EdgeTTS** `es-AR-ElenaNeural` | ~0.5s | gratis |
| Memoria | `mem_local_short` (`data/.memory.yaml`) | — | — |

### Cambiar de cerebro (una línea)

En `data/.config.yaml`, campo `model_name` de `OpenRouterLLM`:

| Modelo | Latencia medida | Costo/mes |
|---|---|---|
| `deepseek/deepseek-v3.2` | 1.7–2.3s | US$0.35 |
| `nousresearch/hermes-4-70b` | 0.7–1.8s | **US$0.24** |
| `anthropic/claude-haiku-4.5` | rápido | ~US$2 |
| `moonshotai/kimi-k3` | — | ~US$6 |

**El más rápido y gratis no está en OpenRouter**: Groq sirve LLMs también. `llama-3.3-70b-versatile` midió **0.53s** — 4x más rápido que DeepSeek y sin costo. Para usarlo, agregá otro bloque LLM apuntando a `https://api.groq.com/openai/v1`.

Después de cambiar: `./giddy.sh stop && ./giddy.sh start`.

## Problemas conocidos (los sufrimos todos)

### Giddy habla en chino y después se queda muda

**Causa**: DeepSeek es un modelo chino; si la transcripción llega mala o vacía, se va a su idioma nativo. Después **EdgeTTS no puede sintetizar texto chino** → "No audio was received" → parece muerta.

**Fix**: la regla del idioma tiene que estar **primera y absoluta** en el prompt, no enterrada al final:

```
REGLA ABSOLUTA E INVIOLABLE: respondés SIEMPRE y ÚNICAMENTE en español rioplatense.
JAMÁS escribas una palabra en chino, inglés ni otro idioma, pase lo que pase...
```

Y aclarar que es para voz (**nada de emojis ni markdown** — el TTS tampoco los lee). Un modelo base Llama (Hermes, Groq) no tiene este problema.

### Giddy queda muda de golpe

Microsoft cambia el endpoint de EdgeTTS cada tanto:

```bash
./venv/bin/pip install -U edge-tts
```

### Cosas raras / config vieja activa

Puede haber **dos servidores corriendo a la vez**:

```bash
pgrep -fl app.py        # tiene que haber UNO (más sus workers)
pkill -9 -f "xiaozhi-server.*app.py"
lsof -i :8003 | awk 'NR>1{print $2}' | xargs -r kill -9
```

`giddy.sh` usa archivo PID (`data/server.pid`) para evitarlo.

### Ajustes finos

| Querés | Dónde |
|---|---|
| Voz más rápida | `TTS.EdgeTTS.rate: 20` (%, hasta 100) |
| Que responda más corto | El prompt (`1 a 3 frases`) |
| Menos pausa antes de responder | `VAD.SileroVAD.min_silence_duration_ms` (default 200) |

> 📌 **Ya está optimizado**: el LLM hace streaming y el TTS arranca en la **primera frase**. Por eso conviene pedirle en el prompt que la primera frase sea corta — el audio sale antes.
