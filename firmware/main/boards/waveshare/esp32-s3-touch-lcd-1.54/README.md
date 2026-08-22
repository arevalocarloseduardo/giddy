# Giddy en Waveshare ESP32-S3 Touch LCD 1.54

Esta variante convierte la placa redonda de 240 x 240 en el dispositivo Giddy.
Usa el avatar `robot-pro_240`, dos accesos tactiles y audio con AEC en el equipo.

## Personalidad visual

- `boot`: presentacion completa al encender.
- `connecting`, `listening` y `speaking`: actividad legible sin depender de texto.
- `curious`, `winking` y `happy`: microgestos espaciados durante el reposo.
- `dozing` y `sleepy`: transicion y respiracion visual al dormir.
- `wake`: despertar al volver a interactuar.
- `goodnight`: despedida antes de bajar la luz y cortar energia.

Las secuencias temporales no bloquean la conversacion. Una emocion explicita puede
interrumpirlas, mientras que los cambios normales de actividad se guardan como el
estado visual que debe aparecer al terminar.

## Compilacion

Desde `firmware/`, con ESP-IDF 6.0.2 disponible:

```bash
python scripts/release.py waveshare/esp32-s3-touch-lcd-1.54 --name esp32-s3-touch-lcd-1.54
```

La coleccion de GIF se genera desde `avatar/generate_faces_pro.py` y se compila
desde `firmware/custom_emoji/robot-pro_240`.

El estado `music` se envia dentro del mensaje `tts.start` cuando el servidor
reproduce una cancion. El firmware mantiene esa animacion hasta que termina o
se interrumpe el audio.

## Hardware

- [Waveshare ESP32-S3-Touch-LCD-1.54](https://www.waveshare.com/esp32-s3-touch-lcd-1.54.htm)

## Controles

- `PLUS`: sube el volumen. Mantener presionado lleva el volumen al 100%.
- `BOOT`: baja el volumen. Mantener presionado activa silencio.
- `PWR`: una pulsacion inicia o detiene la conversacion. Mantener presionado
  durante unos 2 segundos reproduce la despedida y apaga.

La configuracion WiFi no tiene un atajo fisico para evitar activaciones
accidentales. Se inicia desde la herramienta de configuracion con confirmacion.
