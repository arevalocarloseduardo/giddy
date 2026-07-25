# 01 — El hardware

## La placa: Waveshare ESP32-S3-Touch-LCD-1.54

| Componente | Detalle |
|---|---|
| **MCU** | ESP32-S3R8 — doble núcleo Xtensa LX7 @ 240 MHz |
| **Memoria** | 16 MB flash NOR + **8 MB PSRAM** (octal, 80 MHz) |
| **Pantalla** | IPS 1.54" **240×240**, controlador ST7789 (SPI) |
| **Táctil** | Capacitivo CST816 (I2C) |
| **Audio** | Códec **ES8311** + ADC **ES7210** — doble micrófono con **cancelación de eco (AEC)** |
| **Amplificador** | NS4150B + parlante integrado |
| **Sensor** | IMU **QMI8658** (acelerómetro + giroscopio 6 ejes) |
| **Conectividad** | WiFi 2.4 GHz b/g/n + Bluetooth LE 5 |
| **Almacenamiento** | Ranura microSD |
| **Batería** | LiPo 3.7V, conector **MX1.25** (1.25 mm) — carga por USB-C |
| **Botones** | PWR (encendido/hablar) + Volumen ± |
| **USB** | Type-C (USB nativo, no adaptador serie) |

El doble micrófono con AEC es lo que la hace ideal para asistente de voz: puede escuchar mientras el parlante suena.

## La batería

Enchufás una LiPo de 3.7V con conector **MX1.25** y listo: carga sola por el USB-C y conmuta a batería al desconectar.

⚠️ **Ojo con la polaridad**: no todos los proveedores de baterías usan el mismo orden de cables. Verificá contra la serigrafía de la placa **antes** de enchufar.

## Los 3 botones físicos

Son **físicos**, no de la pantalla táctil:

| Botón | Toque corto | Mantenido |
|---|---|---|
| **PWR** | Inicia/corta una charla (= decir "Giddy"). **También corta a Giddy si está hablando de más** | Apaga el dispositivo |
| **Vol +** | Sube volumen | Volumen al máximo |
| **Vol −** | Baja volumen | Silencia |

El de PWR es el más útil: es tu "interrumpir" mientras no tengamos barge-in por voz (ver `docs/03`).

## Conexión a la máquina

Aparece como `/dev/cu.usbmodem101` en macOS (USB nativo).

**Si no aparece**: desenchufá, mantené apretado **BOOT** y enchufá de nuevo — entra en modo descarga.

**Si el puerto queda "ocupado"** y falla el flasheo:

```bash
lsof /dev/cu.usbmodem101 | awk 'NR>1{print $2}' | xargs -r kill -9
```

## Documentación oficial

- [Wiki de Waveshare](https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.54) — pinout, esquemáticos
- [Repo de ejemplos](https://github.com/waveshareteam/ESP32-S3-Touch-LCD-1.54) — demos Arduino + ESP-IDF
