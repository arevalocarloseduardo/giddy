# 05 — Actualizar sin cable (OTA)

Sí, se puede: **el servidor ya tiene el mecanismo OTA y la placa ya lo consulta en cada arranque.** Solo falta usarlo.

En el log del servidor esto aparece en cada boot de la placa:

```
OTA请求设备ID: 28:84:85:91:c0:4c
查找型号 esp32-s3-touch-lcd-1.54 的固ire，找到 0 个候选     ← 0 candidatos: la carpeta está vacía
设备固件已是最新: 2.4.x
```

"0 candidatos" = no hay firmware nuevo publicado. Cuando pongas uno, lo descarga y se auto-flashea.

## Cómo funciona

El servidor busca archivos en `main/xiaozhi-server/data/bin/` con este formato **exacto**:

```
{modelo}_{version}.bin
```

Para esta placa el modelo es `esp32-s3-touch-lcd-1.54`. Ejemplo válido:

```
esp32-s3-touch-lcd-1.54_2.4.6.bin
```

El servidor compara esa versión con la que reporta la placa y, si es mayor, le pasa la URL de descarga.

## El flujo completo

### 1. Subir la versión del firmware

En `xiaozhi-esp32/CMakeLists.txt`:

```cmake
set(PROJECT_VER "2.4.6")     # ← subila SIEMPRE que publiques por OTA
```

> ⚠️ **Este paso no es opcional.** Si publicás un `.bin` como 2.4.6 pero el binario internamente sigue diciendo 2.4.5, la placa lo instala, reporta 2.4.5, el servidor se lo vuelve a ofrecer... **loop infinito de updates**.

### 2. Compilar

```bash
source ~/esp/esp-idf/export.sh
idf.py build
```

### 3. Publicarlo (esto reemplaza al cable)

```bash
mkdir -p ../xiaozhi-esp32-server/main/xiaozhi-server/data/bin
cp build/xiaozhi.bin \
   ../xiaozhi-esp32-server/main/xiaozhi-server/data/bin/esp32-s3-touch-lcd-1.54_2.4.6.bin
```

### 4. Reiniciar la placa

Botón PWR (mantenido para apagar, después encender) o cortando la alimentación. Al arrancar consulta el OTA, ve la versión nueva, la baja por WiFi y se flashea sola.

**Listo — cero cables.**

## ⚠️ Lo que OTA NO actualiza: el avatar

OTA reemplaza la **partición de la app**, no la de **assets** (los ~5 MB de GIFs de la cara, fuentes y modelos de voz).

O sea: si cambiás la cara con `generate_faces_pro.py`, eso **no viaja por OTA**.

Para eso existe una herramienta MCP en el firmware: **`self.assets.set_download_url`** — le pasás una URL desde donde bajar el paquete de assets. Aparece en el log de boot:

```
MCP: Add tool: self.assets.set_download_url [user]
```

Todavía no lo configuramos. Mientras, **cambios de avatar = cable** (y ojo con el corte del flasheo de 5 MB, ver `docs/03`).

Resumen práctico:

| Cambiás… | ¿Necesitás cable? |
|---|---|
| Código del firmware (C++) | ❌ no, va por OTA |
| Configuración (`sdkconfig`) | ❌ no, va por OTA |
| **Los GIFs de la cara** | ✅ sí (hasta configurar la URL de assets) |
| **Nada del firmware** — solo prompt, modelo, voz | ❌ no, eso es del **servidor**: `./giddy.sh stop && start` |

## Lo más importante

**La mayoría de los ajustes no tocan el firmware.** El cerebro, la personalidad, la voz, la velocidad del habla — todo eso vive en el servidor y se cambia editando `data/.config.yaml` + reiniciar. Sin cable y sin compilar.

El cable solo hace falta para el avatar (por ahora) o si algo queda inconsistente y necesitás reflashear todo de cero.
