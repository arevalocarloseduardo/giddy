# 07 — Versiones pineadas (reproducibilidad)

Este repo no incluye los repos de terceros (pesan 3.7 GB) — incluye **parches** que se aplican encima. Para que eso funcione **siempre**, los parches tienen que aplicarse sobre la versión exacta contra la que fueron hechos.

## La tabla que importa

| Repo upstream | Versión pineada | Commit | Cómo clonarlo |
|---|---|---|---|
| [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) (firmware) | **v2.4.0** | tag estable | `git clone --depth 1 -b v2.4.0 ...` |
| [xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) | **v0.9.6** | `f5ed1aa` | `git clone --depth 1 -b v0.9.6 ...` |
| [waveshareteam/ESP32-S3-Touch-LCD-1.54](https://github.com/waveshareteam/ESP32-S3-Touch-LCD-1.54) (ejemplos Arduino) | main | — | sin parches, no importa la versión |

**Los tags no se mueven** — por eso clonando así, `git apply` va a funcionar hoy y en dos años.

⚠️ **Nunca clones `main`** de los dos primeros para aplicar los parches. El upstream sigue avanzando y los archivos que tocamos cambian.

## Cómo actualizar a una versión nueva del upstream (a propósito)

Cuando quieras subir de versión, es un proceso deliberado:

```bash
# 1. Clonar la versión nueva al lado
git clone --depth 1 -b v0.9.7 https://github.com/xinnan-tech/xiaozhi-esp32-server.git server-nuevo
cd server-nuevo

# 2. Intentar aplicar el parche
git apply --3way ../patches/xiaozhi-esp32-server.patch
```

- **Si aplica limpio** → probá que funcione, y actualizá la tabla de arriba con la versión nueva.
- **Si hay conflictos** → resolvelos a mano, y después regenerá el parche:

```bash
git diff > ../patches/xiaozhi-esp32-server.patch
```

Lo mismo para el firmware con su propio parche.

## ¿Por qué parches y no todo el código adentro?

| | Parches + versión pineada (lo que hacemos) | Copiar el código entero adentro |
|---|---|---|
| Peso del repo | **1 MB** | +36 MB (server) +200 MB (firmware) |
| Actualizar upstream | fácil y deliberado | hay que mergear a mano |
| Si el upstream desaparece | ⚠️ te queda el parche sin base | ✅ autocontenido |
| Ver qué cambiamos nosotros | ✅ obvio, es el parche | ❌ mezclado con código ajeno |

El punto débil es el último: **si el upstream se borra, el parche solo no alcanza.**

Si algún día querés blindarte contra eso (razonable si Giddy se vuelve un producto), la opción es guardar una copia del código base en el repo. El server Python son ~6 MB de código real (sin `venv`, `models`, `music` ni `data`). Se puede hacer cuando quieras.

## Lo que NO está en el repo y hay que bajar aparte

Ninguna de estas cosas va a git (pesan y son descargables):

| Qué | Peso | Dónde se explica |
|---|---|---|
| `venv/` del servidor | 1.5 GB | docs/04 |
| Modelos de voz (Vosk, Silero) | 65 MB | docs/04 |
| ESP-IDF + toolchain | ~5 GB | docs/03 |
| `managed_components/` del firmware | se bajan al compilar | docs/03 |
