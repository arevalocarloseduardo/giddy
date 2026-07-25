# 02 — Arrancar con Arduino 🔰

**Este es el camino más simple para probar el hardware.** No es el firmware de Giddy (eso es `docs/03`, con ESP-IDF), pero sirve para verificar que la placa, la pantalla, el micrófono y el IMU funcionan.

## Paso 1 — Instalar

```bash
brew install arduino-cli
```

(O el [Arduino IDE 2.x](https://www.arduino.cc/en/software) si preferís interfaz gráfica. Comparten el mismo core y librerías, así que podés usar los dos.)

## Paso 2 — El core ESP32, versión 3.2.0 (¡importante!)

```bash
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.2.0
```

> ⚠️ **NO actualizar a 3.3.x.** Rompe `GFX_Library_for_Arduino` — cambió la firma de `spiFrequencyToClockDiv` y los ejemplos de Waveshare no compilan.
>
> Si el IDE lo actualiza solo, volvé a anclarlo con el comando de arriba.

## Paso 3 — Clonar los ejemplos y copiar las librerías

```bash
git clone https://github.com/waveshareteam/ESP32-S3-Touch-LCD-1.54.git
mkdir -p ~/Documents/Arduino/libraries
cp -R ESP32-S3-Touch-LCD-1.54/examples/ESP32-S3-Touch-LCD-1.54-demo/Arduino-3.2.0/libraries/* \
      ~/Documents/Arduino/libraries/
```

Eso instala: `lvgl` (8.3.11), `GFX_Library_for_Arduino`, `SensorLib`, `ESP32-audioI2S`, `U8g2`, `OneButton`, `arduinoVNC`.

**Para LVGL hace falta un paso extra** — su config va suelto en la carpeta de librerías:

```bash
cp ESP32-S3-Touch-LCD-1.54/examples/ESP32-S3-Touch-LCD-1.54-demo/Arduino-3.2.0/examples/08_lvgl_arduino_v8/lv_conf.h \
   ~/Documents/Arduino/libraries/lv_conf.h
```

> 📌 La librería incluida es **LVGL 8.3.11** → usá los ejemplos `_v8`. El `09_lvgl_arduino_v9` **no compila** con estas librerías.

## Paso 4 — Compilar y flashear

Desde la carpeta de cualquier ejemplo:

```bash
arduino-cli compile --fqbn "esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi" .
arduino-cli upload -p /dev/cu.usbmodem101 --fqbn "esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi" .
```

**Qué significa cada flag** (si usás el IDE gráfico, poné esto en Tools):

| Flag | Valor | Por qué |
|---|---|---|
| Board | `ESP32S3 Dev Module` | — |
| `CDCOnBoot` | `cdc` (Enabled) | Sin esto no funciona `Serial.println` |
| `FlashSize` | `16M` | La placa tiene 16 MB |
| `PSRAM` | `opi` (OPI PSRAM) | Los 8 MB son octal |
| `PartitionScheme` | `app3M_fat9M_16MB` | 3 MB app + 9 MB datos |

## Ejemplos recomendados (en orden)

En `examples/ESP32-S3-Touch-LCD-1.54-demo/Arduino-3.2.0/examples/`:

| Ejemplo | Qué prueba |
|---|---|
| `04_gfx_helloworld` | ✅ **Empezá acá** — texto en la pantalla |
| `08_lvgl_arduino_v8` | Interfaz gráfica táctil (label + switches) |
| `01_i2s_audio` | Micrófono y parlante |
| `03_qmi8658_example` | El IMU (acelerómetro/giroscopio) |
| `10_esp_sr` | Reconocimiento de voz **offline** |
| `07_sd_card_test` | La microSD |

Los dos primeros están verificados funcionando en esta placa.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| No aparece el puerto | Mantener **BOOT** apretado mientras enchufás |
| Puerto ocupado / falla el upload | `lsof /dev/cu.usbmodem101 \| awk 'NR>1{print $2}' \| xargs -r kill -9` |
| Errores de `spiFrequencyToClockDiv` | Estás en core 3.3.x → volvé a 3.2.0 |
| LVGL no compila | Falta `lv_conf.h` en `~/Documents/Arduino/libraries/` |
| `Serial.println` no imprime nada | Falta `CDCOnBoot=cdc` |
