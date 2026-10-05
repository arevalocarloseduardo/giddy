/* sdkconfig del simulador: lo mínimo que mira el código de display.
 * Debe coincidir con lo que tiene la placa para que se compile la MISMA UI. */
#pragma once

#define CONFIG_BOARD_TYPE_WAVESHARE_ESP32_S3_TOUCH_LCD_1_54 1
#define CONFIG_LANGUAGE_ES_ES 1
#define CONFIG_SPIRAM 1
#define CONFIG_USE_DEVICE_AEC 1
/* CONFIG_USE_WECHAT_MESSAGE_STYLE y CONFIG_USE_MULTILINE_CHAT_MESSAGE
 * NO están definidos, igual que en la placa (subtítulo de una línea). */
/* CONFIG_LV_USE_SNAPSHOT no se define: SnapshotToJpeg necesita el encoder
 * de ESP, acá no hace falta (el simulador saca PNG por su cuenta). */
