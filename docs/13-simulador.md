# 13 — Simulador de la pantalla (sin la placa)

Cada retoque de la cara de Giddy costaba compilar el firmware, flashear ~5 MB de assets por cable y mirar la placa. Ahora hay un simulador que **compila el mismo `lcd_display.cc` del firmware** y lo dibuja en una ventana de la compu con LVGL 9.5 + SDL2. Lo que ves ahí es lo que va a mostrar la placa, GIFs animados y subtítulo incluidos.

La guía completa (compilar, teclas, guiones, cómo está armado) está en **[firmware/simulator/README.md](../firmware/simulator/README.md)**. Acá, lo esencial.

## En 30 segundos

```bash
brew install sdl2 cmake ninja          # Mac. En Linux: libsdl2-dev
cd firmware/simulator
cmake -S . -B build -G Ninja && cmake --build build --parallel
./build/giddy_simulator
```

> Necesita `firmware/managed_components/` (LVGL y las fuentes). Si recién clonaste el repo, corré una vez `idf.py reconfigure` en `firmware/` para que ESP-IDF los baje. Para el simulador en sí no hace falta ESP-IDF.

## Para qué sirve

- **Iterar la cara**: cambiás un GIF en `avatar/robot-pro_240/`, relanzás, lo ves. Sin flashear.
- **Probar el subtítulo**: `u` muestra lo que dijiste vos, `b` lo que responde Giddy, `l` un texto largo para ver el marquee.
- **Capturas automáticas**: `./build/giddy_simulator --headless --script scripts/demo.txt` genera PNGs de todos los estados. Ideal para comparar antes/después de un cambio o para el material de venta.
- **Desarrollar la UI que falta** (boca que se mueve al hablar, colores distintos por quién habla) con ciclos de segundos en vez de minutos.

## Lo que no simula

Audio, wake word, red y el loop de `application.cc`. Si el cambio toca eso, sigue haciendo falta la placa. La regla: **lo que se ve bien en el simulador se ve igual en la placa**; lo que suena o escucha, se prueba en la placa.

## Idea robada de Meta

El esquema (LVGL + SDL + stubs chiquitos de ESP-IDF) lo usa el [Muse Gadgets SDK](https://github.com/facebookincubator/muse-gadget-sdk) de Meta para su UI. Es la única pieza de ese proyecto que nos sirvió: el resto está atado a la nube de Meta.
