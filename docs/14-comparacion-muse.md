# 14 — Giddy vs. Muse Gadgets (Meta): comparación de arquitectura

Octubre 2026. Meta liberó el firmware ESP32 de sus "Muse Gadgets" bajo Apache 2.0 ([repo](https://github.com/facebookincubator/muse-gadget-sdk)). Leímos el código completo de los dos lados (firmware Muse ~45K líneas de C/C++ reales, firmware Giddy ~25K, más el server de Giddy) para responder tres preguntas: **qué hace mejor cada uno, qué conviene robarle a Muse, y qué no**.

Resumen en una línea: **Muse es mejor firmware de IoT; Giddy es mejor asistente de voz.** Muse resuelve bien lo que a un producto vendible le falta (emparejamiento, seguridad, actualizaciones, diagnóstico), pero su parte de voz es primitiva y está atada a la nube de Meta. Lo correcto es quedarse con la arquitectura de Giddy y copiarle a Muse las piezas de "producto".

---

## 1. Comparación por tema

| Tema | Giddy (xiaozhi + nuestro fork) | Muse Gadgets | Mejor |
|---|---|---|---|
| **Activación por voz** | Wake word local (MultiNet, "giddy" y variantes), manos libres | **Push-to-talk con botón.** Sin wake word, sin VAD | **Giddy** |
| **Audio** | Opus 16 kHz / 60 ms, AEC + VAD en el chip (AFE de esp-sr) con canal de referencia, **barge-in real** | WAV crudo en base64 por JSON, máx. 15 s. Sin AEC propio (depende del DSP XMOS de placas Seeed) | **Giddy** |
| **Respuesta** | Voz (TTS en el server, arranca en la primera frase) + subtítulo + cara | **Solo texto en pantalla.** El TTS "lo integrás vos" | **Giddy** |
| **Cerebro** | El que queramos: Hermes local, Groq, OpenRouter, Ollama. Router gratis/pago | Solo Muse de Meta. Sin backend propio | **Giddy** |
| **Latencia percibida** | Respuestas enlatadas <150 ms, pistas habladas, caché de voz | No aplica (texto) | **Giddy** |
| **Emparejamiento / Wi-Fi** | Hotspot **abierto** "Xiaozhi-XXXX" + portal cautivo + código de 6 dígitos **hablado** | **BLE desde el celular**, ECDH P-256 + AES-GCM, confirmación con botón físico, hasta 8 redes guardadas con canal/BSSID cacheado | **Muse** |
| **Identidad del dispositivo** | MAC + UUID autogenerado; token bearer opcional; el server acepta cualquier device-id | Token de acceso/refresh por dispositivo, refresh automático cada 30 días, firma eFuse opcional | **Muse** |
| **Canal al servidor** | `ws://` **en claro** a una IP fija de la LAN grabada en el firmware | TLS + Noise XX (X25519/AES-GCM) + reconexión con backoff 1→15 s | **Muse** (aunque su Noise agrega poco sobre TLS: no pinea claves) |
| **Actualizaciones (OTA)** | A/B con rollback ✅, pero **sin firma**, validación de imagen desactivada, `upgrade_firmware(url)` invocable por cualquiera | Firma RSA + rollback con verificación a los 300 s. Debilidad: clave de firma dev commiteada | **Muse** |
| **Assets (caras, fuentes)** | Partición de 8 MB, se reescribe **en el lugar** con checksum de 16 bits; confirmación en el siguiente hello ✅ | No tiene: el avatar es código C procedural | **Giddy** (idea) / Muse (robustez) |
| **Credenciales guardadas** | NVS **sin cifrar** (Wi-Fi, tokens) | NVS cifrado con clave HMAC en eFuse (opcional, aborta si falla) | **Muse** |
| **Diagnóstico remoto** | Logs por serie. Sin core dump, sin razón de reset, sin reporte | Ring de 16 KB en PSRAM, reporte JSON con reset reason, heap, RSSI, estado OTA | **Muse** |
| **Extensibilidad (tools)** | MCP JSON-RPC completo, paginado, con validación de tipos | `link.register` con esquema por comando, límite 8 KB, sin validación | **Giddy** |
| **Cara / avatar** | 33 GIFs hechos a mano (1.9 MB), decoder propio | Pixel-art **procedural** 64×64 en C: cero bytes de assets, reacciona al nivel de audio, pero tope de 32 colores y la edita un LLM | **Giddy** en calidad visual; Muse en reactividad |
| **Subtítulos** | Una línea con marquee | Páginas de 2–3 líneas sincronizadas con la **posición de reproducción del audio**; pliega acentos a ASCII (ñ→n) | **Muse** (idea) |
| **Pantalla 240×240** | Diseñado para esta pantalla | Caería en su "modo compacto": sin anillo, sin VU, 2 líneas | **Giddy** |
| **Ahorro de energía** | PowerSaveTimer, deep sleep por botón, apagado a los 5 min en batería | Light sleep con esp_pm en 6 placas, modem sleep; el core no ahorra nada | Empate |
| **Simulador de UI** | `firmware/simulator/` (docs/13): compila la UI real, capturas por guion | Igual idea, más **reloj virtual determinista + tests por hash** en CI | **Muse** (lo copiamos a medias) |
| **Tests** | 3 archivos Python de release; 119 tests en el server | ~45 tests de host que compilan el C real con fakes, vectores criptográficos, matriz de placas en CI | **Muse** |
| **Memoria** | Correcto | Disciplina notable: PSRAM primero, "gates" de headroom DMA, tamaños por placa, telemetría de heap | **Muse** |
| **Licencia / dependencia** | Todo nuestro, servidor propio | Apache 2.0 pero **inútil sin la nube de Meta**; términos del token: personal y no comercial, máx. 50 dispositivos | **Giddy** |

---

## 2. Lo que Muse hace peor (y por qué no conviene migrar)

- **No es un asistente de voz.** Apretás, hablás hasta 15 s, Muse transcribe y responde texto. Para un producto que habla y escucha manos libres, el camino de xiaozhi (AFE + wake word + Opus + TTS streaming) está años adelante.
- **Lock-in total.** `hatch.metaaivm.com`, `api.muse.ai`, el protobuf del servidor y el token SDK están cableados. Los términos prohíben uso comercial.
- **Un `app.c` de 2.800 líneas** sin máquina de estados formal: flags en NVS, strings de etapa y contadores de generación. El `Application` de xiaozhi, con transiciones en lista blanca, es más sano.
- **El avatar procedural** se ve peor que nuestros GIFs y la "edición" es pedirle a un LLM que reescriba C. Hasta Meta guarda una tabla de frames derivada de un GIF para sus placas ST7789.
- **Tunnel de red sin filtro**: la VM de Meta ve toda tu LAN y sale a internet con tu IP. Técnicamente interesante, pero como producto es un riesgo que no queremos.

## 3. Lo que vale la pena robarle (en orden de valor para vender Giddy)

| # | Qué | De dónde (Muse) | Qué cambia en Giddy | Esfuerzo |
|---|---|---|---|---|
| 1 | **Emparejamiento por BLE desde el celular** con confirmación por botón | `main/ble_server.c`, `link_pairing.c`, `pairing_transcript.c` (ECDH P-256 + HKDF + AES-GCM, chunks de 160 B) | Reemplaza el hotspot abierto "Xiaozhi" y el código hablado. El mismo canal lleva Wi-Fi + token del server. Es **la** diferencia entre "proyecto" y "producto" | 1–2 semanas (firmware + una pantalla en el portal/app) |
| 2 | **Identidad por dispositivo + canal cifrado** | Patrón de tokens access/refresh de `vm_api.c`; o simplemente `wss://` con CA pineada | Hoy el server acepta cualquier device-id en `ws://`. Mínimo viable: `wss` + token por dispositivo emitido en el emparejamiento, y **hacer cumplir** `user_only` en MCP | 3–5 días |
| 3 | **OTA firmada + NVS cifrado** | `ota.c` + `BOOTLOADER_APP_ROLLBACK` + `SECURE_SIGNED_ON_UPDATE`; `CONFIG_HOMEHUB_NVS_ENCRYPTION` | Activar firma de imagen (ya tenemos A/B), firmar también los paquetes de assets con SHA-256, cifrar NVS | 2–3 días + gestión de la clave |
| 4 | **Reporte de fallas** | `diagnostic_log.c` + `bug_report.c` | Ring de log en PSRAM, reset reason, heap y RSSI enviados en el siguiente hello. Core dump a flash. Sin esto no se puede dar soporte a un cliente | 2–3 días |
| 5 | **Subtítulo paginado por posición de audio** | `muse_chat_text.c`, `muse_chat_session.cpp:2154` | Páginas de 2–3 líneas con una línea de solapamiento, la página la elige cuánto audio se reprodujo. Resuelve "el texto pasa muy rápido" sin marquee. **Ojo**: usar fuente Latin-1, Muse pliega acentos | 1–2 días (probar en el simulador) |
| 6 | **Overlay reactivo al audio** | `muse_pixel.c` + `muse_ui.c:1503` (ataque rápido 0.6 / caída lenta 0.2) | Encima del GIF de "speaking": aura o boca modulada por el nivel real de audio, colores de acento por estado | ~1 día |
| 7 | **Simulador determinista con tests por hash** | `simulator/sim_platform.c` (reloj virtual), `tests/test_simulator.py` | Nuestro simulador ya existe; agregarle reloj virtual y un ctest que renderice cada escenario dos veces y compare SHA-256. Cero "golden images" que mantener | 1–2 días |
| 8 | **Vocabulario de estados** | `led_status.c:1041` y `AGENTS.md` "First boot and pairing" | Tabla clara color/animación ↔ estado (emparejando, conectando, error). Útil para el manual de usuario y la cara | medio día |
| 9 | **Multi-red Wi-Fi con caché de canal/BSSID** | `wifi_known.c`, `app.c:449` | Giddy guarda 10 redes pero sin caché; conexión más rápida al encender | 1 día |

**No robar**: el tunnel L3, el avatar procedural, el protocolo Noise tal cual (sin pineo no suma sobre TLS), el `app.c` monolítico.

---

## 4. Problemas de Giddy que salieron al comparar

Encontrados leyendo nuestro propio firmware con la vara de Muse. Verificados en el código:

| Severidad | Dónde | Qué pasa |
|---|---|---|
| ✅ cerrado 2.4.19 (era 🔴) | `main/mcp_server.cc` | Las tools `user_only` (`upgrade_firmware(url)`, `reboot`, `assets.set_download_url`) solo se **ocultan** del listado; `DoToolCall` no verifica el flag. Cualquiera que hable con el websocket puede flashear un firmware desde cualquier URL |
| ✅ cerrado 2.4.19 (era 🔴) | `sdkconfig.defaults`, OTA | Antes: `BOOTLOADER_SKIP_VALIDATE_ALWAYS=y` y sin firma. Ahora: firma RSA-3072 obligatoria en OTA (`SECURE_SIGNED_ON_UPDATE_NO_SECURE_BOOT`) y validación al arrancar. Sigue sin Secure Boot por hardware (protege por red, no físico) |
| ✅ cerrado 2.4.19 (era 🔴) | `wifi_board.cc` | Hotspot ahora `Giddy-XXXX` con clave WPA2 de 8 dígitos por equipo, mostrada en pantalla |
| 🟠 Crash | `protocols/websocket_protocol.cc:245` | Un hello del server sin campo `transport` desreferencia un puntero nulo |
| 🟠 Crash | `ota.cc:423` | `std::stoi` sobre la versión: una versión no numérica tira excepción |
| 🟠 Crash | `settings.cc:13` | `ESP_ERROR_CHECK` sobre `nvs_commit`: un fallo de escritura reinicia el equipo |
| 🟡 Producto | `sdkconfig.defaults:96` | `CUSTOM_WAKE_WORD_THRESHOLD=2` (de 100): muy bajo, propenso a despertares falsos. Vale la pena medirlo |
| 🟡 Producto | `giddy_display.cc:758` | `SetControlsVisible` ignora el argumento y siempre oculta: el dashboard táctil y las acciones rápidas quedaron inalcanzables (parece deliberado, pero es código muerto) |
| 🟡 Producto | board | No hay reset de fábrica (`SystemReset` no se crea en esta placa) |
| 🟡 Server | `config.yaml` | `server.auth.enabled: false`; firmware y assets servidos por `http://` sin firma; token del portal viaja en claro y en la URL |

---

## 5. Plan sugerido

1. **Ahora, barato (1 semana):** cerrar los 🔴 y 🟠 de la tabla anterior. ✅ Los tres 🔴 se cerraron en la 2.4.19 (`user_only` cumplido, OTA firmada, hotspot con clave). Quedan los tres crashes 🟠.
2. **Antes de la primera serie (3–4 semanas):** emparejamiento BLE + identidad por dispositivo + `wss`. Es lo que un cliente va a sentir en los primeros 5 minutos con la caja.
3. **Después, con el simulador:** subtítulo paginado, overlay reactivo, tests deterministas. Es UX, se itera en la compu.
4. **Siempre:** reporte de fallas en el siguiente hello. El día que un cliente diga "se quedó tildado", es la única forma de saber qué pasó.

Lo que queda claro al final: Giddy ya tiene resuelto lo difícil de un asistente de voz. Lo que le falta es la capa de "producto" que Meta, con equipo de hardware de verdad, hizo primero. Esa capa está en Apache 2.0, con tests, y se puede copiar pieza por pieza.

---

### Fuentes

- Código: `tmp/muse-gadget-sdk/esp32` (clonado 2026-10-05), `firmware/main`, `server/`.
- Términos del token SDK y disponibilidad: ver docs/13 y [remio.ai](https://www.remio.ai/post/meta-muse-gadgets-are-open-source-but-the-platform-is-not), [mixed-news](https://mixed-news.com/en/meta-muse-gadgets-sdk-open-source-home-link-esp32-c5/).
