# 06 — Hermes Agent como cerebro (en la PC con GPU)

## La idea

Que el cerebro de Giddy sea **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (el CLI de Nous Research, ⭐220k) corriendo en tu máquina: memoria persistente en disco, skills que crecen con el uso, capacidad de ejecutar tareas multi-paso en archivos y web.

## Lo que hay que saber antes

**1. Hermes Agent no expose una API para que otros lo llamen.** Consume proveedores OpenAI-compatibles (OpenRouter, Ollama, etc.) y sus interfaces son el CLI y el gateway de mensajería (Telegram/Discord/Slack). Revisé el ecosistema comunitario (`awesome-hermes-agent`, `hermes-ecosystem`): las "surfaces" que existen son de control (escritorio/móvil/browser), **ninguna es un endpoint OpenAI-compatible**.

→ **Hay que escribir un puente.** Un servidor HTTP chico que exponga `/v1/chat/completions` y por dentro maneje Hermes.

**2. Un agente es más lento que un chat, por diseño.** Hermes piensa en varios pasos y puede llamar herramientas: una pregunta simple puede tardar **3-10s** (vs 0.5s de Groq). Optimiza **capacidad**, no velocidad.

→ **Diseño recomendado: dos cerebros con ruteo.** Charla simple → Groq (rápido, gratis). Pedidos de tarea/memoria → Hermes.

**3. Requisitos**: el modelo necesita **function calling** y contexto de **≥64K en Ollama**. Picks 2026: **Qwen3 14B** en 12-16 GB VRAM, **Hermes 4.3 36B** en 24 GB. En una Mac M1 de 8 GB no entra.

**4. Podés tener Hermes sin GPU**: el agente corre local (memoria, skills, identidad = tuyas) pero el modelo piensa por **OpenRouter**. Da lo agéntico hoy, sin comprar nada y sin PC prendida 24/7. Después cambiás el proveedor a Ollama sin rehacer nada.

---

## 📋 Prompt para pasarle a Claude en la PC con GPU

Copiá y pegá esto tal cual:

```
Quiero usar Hermes Agent (el CLI de Nous Research, github.com/NousResearch/hermes-agent)
como cerebro de mi asistente de voz. Necesito que me lo instales y me escribas un puente.

CONTEXTO
- Tengo un asistente de voz llamado Giddy corriendo en una placa ESP32-S3.
- El servidor es xiaozhi-esp32-server (Python) y corre en otra máquina de mi red
  (una Mac, IP 192.168.0.51). Ese servidor pide el cerebro por HTTP a un endpoint
  OpenAI-compatible.
- Esta PC tiene GPU y quiero que Hermes Agent corra acá.

TAREA 1 — Instalar Hermes Agent
- Instalalo (en Windows: iex (irm https://hermes-agent.nousresearch.com/install.ps1) —
  el instalador trae uv, Python 3.11, Node.js, ripgrep y ffmpeg).
- Corré `hermes setup`. Configuralo primero con un modelo por OpenRouter para probar
  rápido (te paso la clave aparte), y dejame documentado cómo cambiarlo a Ollama local.
- Verificá que funciona por CLI antes de seguir.

TAREA 2 — Decidir el modelo local según mi GPU
- Fijate qué GPU y cuánta VRAM tengo (nvidia-smi).
- El modelo tiene que soportar FUNCTION CALLING y hay que subir el contexto de Ollama
  a 64K mínimo (sin eso Hermes no funciona bien).
- Referencias: Qwen3 14B para 12-16 GB; Hermes 4.3 36B para 24 GB.
- Decime si mi GPU alcanza y con qué cuantización.

TAREA 3 — Escribir el puente (lo importante)
Un servidor HTTP local que exponga un endpoint OpenAI-compatible y por dentro hable
con Hermes Agent:

- Endpoint: POST /v1/chat/completions, escuchando en 0.0.0.0 (la Mac tiene que poder
  llegarle por la red local; abrí el puerto en el firewall de Windows).
- Request: formato OpenAI estándar → {model, messages[], stream, max_tokens}.
- IMPORTANTE: tiene que soportar streaming SSE, porque el cliente manda "stream": true
  y va leyendo chunks. Devolvé chunks con el formato de OpenAI
  (data: {"choices":[{"delta":{"content":"..."}}]}\n\n ... y cierre con data: [DONE]).
  Si no podés streamear de verdad, al menos emulá un stream de un solo chunk.
- Sesión PERSISTENTE de Hermes: NO levantes el CLI de cero en cada mensaje o la latencia
  explota. Mantené una sesión viva (proceso persistente, su RPC, o lo que Hermes exponga)
  y reusala entre requests.
- El system prompt viene en messages[0] — respetalo (define la personalidad de Giddy).
- Devolvé solo el texto final de Hermes, sin ruido de terminal, sin ANSI, sin logs de
  tools. Es para leerse en voz alta por un parlante.
- Loguea la latencia de cada request así puedo medir.

TAREA 4 — Probarlo
Verificá con curl que responde bien, en streaming y no-streaming:

  curl http://localhost:PUERTO/v1/chat/completions -H "Content-Type: application/json" \
    -d '{"model":"hermes","messages":[{"role":"system","content":"Sos Giddy, asistente argentina. Respondes SOLO en español, 1-2 frases cortas, sin emojis ni markdown."},{"role":"user","content":"hola, como andas?"}],"stream":true}'

Decime la latencia medida y la IP:puerto final, que los necesito para configurar el
servidor del asistente.

RESTRICCIONES
- Las respuestas son para VOZ: texto plano, sin emojis, sin markdown, sin listas.
- No metas claves API en ningún archivo que vaya a git.
- Dejame un README con cómo arrancar/parar todo y cómo cambiar de modelo.
```

---

## Cuando la otra máquina termine

Te va a dar una **IP:puerto**. Con eso, en la Mac, agregás un bloque al `data/.config.yaml` del servidor:

```yaml
LLM:
  HermesLocal:
    type: openai
    model_name: hermes
    url: http://IP_DE_LA_PC:PUERTO/v1
    api_key: no-hace-falta      # el puente es local, sin auth
```

Y en `selected_module` cambiás `LLM: HermesLocal`. Reiniciás con `./giddy.sh stop && start` y listo.

## El paso siguiente: los dos cerebros

Con Hermes andando, lo ideal es el ruteo:

| Le decís | Va a | Tarda |
|---|---|---|
| "hola", "contame un chiste" | **Groq** | 0.5s |
| "acordate que...", "buscame X", "mandame Y" | **Hermes** | 3-10s, pero *hace* cosas |

Eso requiere un pequeño router del lado del servidor de la Mac (decide por palabras clave o preguntándole al modelo rápido). Es la mejor versión de Giddy: ágil para charlar, potente cuando hace falta.
