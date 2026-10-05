# Simulador de la pantalla de Giddy

Dibuja en una ventana de la compu **exactamente** lo que muestra la placa: compila el mismo
`main/display/lcd_display.cc`, los mismos temas, fuentes y GIFs del avatar, con LVGL 9.5
(el mismo árbol de `managed_components/`) y SDL2 como "pantalla".

Sirve para iterar la cara, los subtítulos y los estados en segundos, sin compilar el
firmware ni flashear 5 MB de assets. Y para sacar capturas PNG automáticas.

Lo que **no** simula: audio, wake word, red, el loop de `application.cc`. Eso sigue
necesitando la placa.

## Requisitos

- CMake ≥ 3.20, Ninja, clang o gcc con C++17
- SDL2 (`brew install sdl2` en Mac; `sudo apt install libsdl2-dev` en Linux)
- Haber compilado el firmware **una vez** (`idf.py build` o `idf.py reconfigure`) para que
  exista `managed_components/` con LVGL y las fuentes. No hace falta ESP-IDF para el
  simulador en sí.

## Compilar

```bash
cd simulator
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel
```

## Usar

### Ventana interactiva

```bash
./build/giddy_simulator
```

| Tecla | Hace |
|---|---|
| ← / → | cara anterior / siguiente (imprime el nombre en la terminal) |
| 1..9 | caras 1..9 de la lista |
| u | subtítulo del usuario |
| b | subtítulo del bot |
| l | texto largo (prueba el marquee) |
| c | limpiar subtítulo |
| i / e / h | estado idle / escuchando / hablando |
| s | captura `giddy-N.png` |
| q / Esc | salir |

### Capturas automáticas (sin ventana)

```bash
./build/giddy_simulator --headless --script scripts/demo.txt
```

El guion es una línea por comando:

```
emotion happy          # cualquier GIF del avatar (neutral, thinking, sleepy, ...)
user TEXTO             # subtítulo como si hablaras vos
bot TEXTO              # subtítulo como si hablara Giddy
clear                  # borra el subtítulo
state speaking         # idle | listening | speaking | connecting | starting
battery 15             # nivel de batería (agregá "charging" si carga)
status TEXTO           # barra de estado (oculta en la UI de Giddy)
notify TEXTO           # notificación (ídem)
wait 800               # milisegundos
shot out/archivo.png   # captura
quit
```

Una sola captura rápida: `./build/giddy_simulator --headless --emotion happy --shot happy.png`

### Otras opciones

`--zoom 3` (la ventana es 240×240, el zoom la agranda), `--emoji-dir DIR` (otro set de GIFs),
`--quiet` (menos log).

## Cómo está armado

```
simulator/
├── CMakeLists.txt    compila main/display/** + fuentes + LVGL del firmware
├── lv_conf.h         réplica de lo que el firmware configura por Kconfig + LV_USE_SDL
├── compat/           stubs de ESP-IDF: esp_log, esp_timer (sobre lv_timer), esp_pm,
│                     heap_caps, esp_lvgl_port, Settings en memoria, Board/Application fake
├── src/main.cc       ventana SDL, carga del avatar, guion, teclas, captura PNG
├── src/sim_esp.cc    implementación de los stubs
├── src/sim_sounds.cc símbolos vacíos de los .ogg que embebe la placa
└── scripts/demo.txt  guion de ejemplo
```

La regla de oro: **el simulador no copia código del display**. Si el firmware cambia
`lcd_display.cc`, el simulador lo refleja al recompilar. Si algo se ve distinto acá que en
la placa, es un bug del simulador (probablemente en `lv_conf.h` o `compat/sdkconfig.h`).

## Problemas típicos

| Síntoma | Solución |
|---|---|
| `No encuentro LVGL en .../managed_components` | compilá el firmware una vez (`idf.py reconfigure`) |
| `sin GIFs del avatar` | pasá `--emoji-dir ../custom_emoji/robot-pro_240` o `../../avatar/robot-pro_240` |
| Ventana negra en headless | normal: usa el driver `dummy` de SDL, mirá los PNG |
| `lv_anim_speed_clamped: max_time is truncated` | aviso inofensivo del marquee, pasa igual en la placa |
