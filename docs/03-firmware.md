# 03 — El firmware de Giddy (ESP-IDF)

Este es el firmware real: wake word local, cara animada a pantalla completa, conexión al servidor propio.

Base: [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) v2.4.0 + nuestros parches.

## Paso 1 — ESP-IDF v6.0.2

```bash
mkdir -p ~/esp && cd ~/esp
git clone --depth 1 --shallow-submodules --recursive -b v6.0.2 https://github.com/espressif/esp-idf.git
cd esp-idf && ./install.sh esp32s3
```

Después, **en cada terminal nueva**:

```bash
source ~/esp/esp-idf/export.sh
```

## Paso 2 — Clonar y aplicar nuestros parches

```bash
git clone --depth 1 -b v2.4.0 https://github.com/78/xiaozhi-esp32.git
cd xiaozhi-esp32
git apply ../patches/xiaozhi-esp32.patch
cp -R ../avatar/robot-pro_240 custom_emoji/
cp ../avatar/generate_faces*.py custom_emoji/
```

## Paso 3 — Compilar y flashear

```bash
IDF_TARGET=esp32s3 idf.py reconfigure   # solo la primera vez
idf.py build                            # ~8 min la primera
idf.py -p /dev/cu.usbmodem101 flash
```

> ⚠️ **NUNCA usar `idf.py set-target`.** Su `fullclean` interno crashea (FileNotFoundError en `build/log`) y deja procesos huérfanos que corrompen builds posteriores con errores tipo "sdkconfig.h: No such file".
>
> Si pasa: `pkill -9 -f idf.py; pkill -9 -f cmake; rm -rf build` y usá `IDF_TARGET=esp32s3 idf.py reconfigure`.

> 📌 Si compilás desde un agente con sandbox (Claude Code), los builds fallan con *"Current working directory cannot be established"*. Hay que correr `idf.py` con el sandbox desactivado.

## Qué cambian nuestros parches

### Configuración (`sdkconfig.defaults`)

```
CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54=y
CONFIG_LANGUAGE_ES_ES=y                    # español
CONFIG_USE_DEVICE_AEC=y                    # cancelación de eco (doble mic)
CONFIG_OTA_URL="http://TU_IP:8003/xiaozhi/ota/"   # ← tu servidor
CONFIG_USE_CUSTOM_WAKE_WORD=y
CONFIG_CUSTOM_WAKE_WORD="fei er nan da;fen nan da"
CONFIG_CUSTOM_WAKE_WORD_THRESHOLD=12
```

### Wake word "Giddy" (MultiNet, dos pronunciaciones)

El wake word custom usa **MultiNet** (reconocimiento fonético), no los modelos fijos. La fonética va en pinyin y el `;` separa variantes — eso último requiere un parche en `scripts/build_default_assets.py` (el script original mete todo como un comando único).

Al bootear el log confirma: `2 active speech commands`.

> ⚠️ **Costo de tener nombre propio: no se puede interrumpir por voz.** En `application.cc` la detección durante el habla solo sigue activa con wake word **AFE** (`EnableWakeWordDetection(IsAfeWakeWord())`), y el nuestro es MultiNet. **Se interrumpe con el botón PWR** (funciona). Si algún día querés interrupción por voz, hay que volver al wake word AFE ("Hi ESP") y perder el nombre custom.

### Cara a pantalla completa (`lcd_display.cc`)

- Tema **"dark" hardcodeado** en el constructor (ignora lo guardado en NVS — había quedado "light" y salían franjas blancas)
- `top_bar_` y `status_bar_` con `LV_OBJ_FLAG_HIDDEN` → sin wifi/hora/batería en pantalla
- Subtítulo de **una sola línea** con marquesina de **una pasada** (`lv_anim_set_repeat_count(&a, 1)`)
- Fuente `font_noto_sans_basic_16_4` (chica, como subtítulo)

> 📌 **`lcd_display.cc` tiene DOS `SetupUI()`**: la de `#if CONFIG_USE_WECHAT_MESSAGE_STYLE` (~línea 356, **no** compila con nuestra config) y la real en el `#else` (~línea 825). **Parchear siempre la segunda.**

### Ahorro de energía (board `.cc`)

```cpp
power_save_timer_ = new PowerSaveTimer(-1, 300, -1);
```

Antes era `(-1, 60, 300)` → **se apagaba sola a los 5 minutos**. Ahora solo atenúa la pantalla y **nunca** auto-apaga (el tercer parámetro en -1). Un asistente tiene que estar siempre a la escucha.

## El avatar animado

22 GIFs de 240×240 (21 emociones + `robot_2` = standby) en `custom_emoji/robot-pro_240/`, generados por `generate_faces_pro.py` (Pillow).

El firmware los anima con su **propio decodificador** (`main/display/lvgl_display/gif/gifdec.c`) — no necesita `CONFIG_LV_USE_GIF`.

**Diseño v5**: ojos rellenos con gradiente vertical + brillo especular, boca por emoción. Anti-banding para RGB565: glow ceñido, paleta fijada a la grilla 5-6-5 (`snap565()`) y dither **Floyd-Steinberg** (el Bayer ordenado dejaba grilla visible).

**Regenerar y reflashear**:

```bash
cd custom_emoji && python3 generate_faces_pro.py     # requiere Pillow
cd .. && rm build/generated_assets.bin && idf.py build
```

> ⚠️ El `rm` es obligatorio: el glob de dependencias de CMake no ve el directorio custom, así que sin borrar el .bin no regenera.

## Problema conocido: el flasheo de assets se corta

El `generated_assets.bin` pesa ~5 MB y la escritura larga por USB-CDC nativo se corta seguido (*"No more data to read from the serial port"*). Workaround — reflashear **solo esa partición** a baud más bajo:

```bash
python -m esptool --chip esp32s3 -p /dev/cu.usbmodem101 -b 230400 \
  --before default-reset --after hard-reset write-flash \
  --flash-mode dio --flash-size 16MB --flash-freq 80m \
  0x800000 build/generated_assets.bin
```

(El resto del firmware normalmente sí queda bien flasheado.)

## Verificar que arrancó bien

```bash
idf.py -p /dev/cu.usbmodem101 monitor
```

Deberías ver:

```
App version: 2.4.x
Board: SKU=esp32-s3-touch-lcd-1.54
StateMachine: State: activating -> idle
CustomWakeWord: Command: fei er nan da, Text: Giddy, Action: wake
2 active speech commands
```

Salir del monitor: `Ctrl+]`
