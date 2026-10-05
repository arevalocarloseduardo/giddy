#pragma once
#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct esp_lcd_panel_t* esp_lcd_panel_handle_t;
esp_err_t esp_lcd_panel_draw_bitmap(esp_lcd_panel_handle_t p, int x1, int y1, int x2, int y2,
                                    const void* data);
esp_err_t esp_lcd_panel_disp_on_off(esp_lcd_panel_handle_t p, bool on);
esp_err_t esp_lcd_panel_del(esp_lcd_panel_handle_t p);

#ifdef __cplusplus
}
#endif
