#pragma once
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct esp_lcd_panel_io_t* esp_lcd_panel_io_handle_t;
esp_err_t esp_lcd_panel_io_del(esp_lcd_panel_io_handle_t io);

#ifdef __cplusplus
}
#endif
