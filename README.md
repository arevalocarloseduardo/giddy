# Giddy — asistente de voz IA en hardware propio

Asistente de voz con cara animada corriendo en una **Waveshare ESP32-S3-Touch-LCD-1.54**, con servidor propio (nada pasa por servicios de terceros salvo los modelos que elijas).

Decís **"Giddy"** y te responde en español argentino, con una cara de robot que muestra emociones.

```
   🗣️  vos hablás
        ↓
   [ Placa ESP32-S3 ]  ← wake word local "Giddy" (no manda audio hasta oírlo)
        ↓ WiFi
   [ Servidor propio ]  ← corre en tu máquina
        ├─ 👂 ASR    Groq Whisper turbo   (~0.4s)
        ├─ 🧠 LLM    OpenRouter / Ollama  (configurable)
        └─ 🗣️ TTS    EdgeTTS es-AR       (voz argentina)
        ↓
   🔊  Giddy contesta + mueve la cara
```

## Qué hay en este repo

| Carpeta | Qué es |
|---|---|
| `docs/` | **Toda la documentación.** Empezá por acá. |
| `server/` | El servidor completo, con nuestros cambios ya aplicados |
| `firmware/` | El firmware completo, con nuestros cambios ya aplicados |
| `avatar/` | Generadores Python de la cara animada + los 22 GIFs listos |
| `patches/` | Nuestros cambios sobre los repos upstream (firmware y servidor) |
| `config/` | Plantilla de configuración del servidor (sin claves) |
| `scripts/` | `giddy.sh` — arrancar/parar el servidor |

**Todo el código necesario está en el repo** (`server/` y `firmware/`): clonás y funciona, sin depender del upstream. Los parches en `patches/` quedan como registro de qué cambiamos respecto de los repos originales.

## Por dónde empezar

1. **[docs/01-hardware.md](docs/01-hardware.md)** — la placa, qué trae, la batería
2. **[docs/02-arduino.md](docs/02-arduino.md)** — 🔰 **arrancar con Arduino** (lo más simple, para probar el hardware)
3. **[docs/03-firmware.md](docs/03-firmware.md)** — el firmware real de Giddy (ESP-IDF)
4. **[docs/04-servidor.md](docs/04-servidor.md)** — el servidor (cerebro, oído, voz)
5. **[docs/05-ota-sin-cable.md](docs/05-ota-sin-cable.md)** — actualizar **sin enchufar el cable**
6. **[docs/06-hermes-otra-maquina.md](docs/06-hermes-otra-maquina.md)** — plan para Hermes Agent en la PC con GPU
7. **[docs/07-versiones.md](docs/07-versiones.md)** — 🔒 versiones del upstream de las que partimos
8. **[docs/08-instalar-en-windows.md](docs/08-instalar-en-windows.md)** — 🪟 **levantar todo en la PC Windows**

## ⚠️ Sobre las claves API

**Este repo no contiene claves reales**, ni siquiera siendo privado. Motivo: el historial de git es para siempre — si alguna vez agregás un colaborador, lo hacés público o cloná en otra máquina, la clave queda expuesta y hay que rotarla.

En `config/config.yaml.example` están los lugares marcados con `TU_CLAVE_..._ACA`. Al instalar en otra máquina, copiás ese archivo y pegás las claves a mano (ver `docs/04`).

Claves que usa Giddy hoy: **OpenRouter** (cerebro) y **Groq** (oído). Las dos tienen capa gratuita o costo de centavos.
