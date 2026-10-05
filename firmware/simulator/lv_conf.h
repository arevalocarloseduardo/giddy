/**
 * lv_conf.h del simulador de Giddy.
 * Replica lo que el firmware configura por Kconfig (sdkconfig: CONFIG_LV_*),
 * más el driver SDL para dibujar en una ventana de escritorio.
 * Todo lo que no está acá toma el default de lv_conf_template.h.
 */
#ifndef LV_CONF_H
#define LV_CONF_H

#define LV_COLOR_DEPTH 16

#define LV_USE_STDLIB_MALLOC  LV_STDLIB_CLIB
#define LV_USE_STDLIB_STRING  LV_STDLIB_CLIB
#define LV_USE_STDLIB_SPRINTF LV_STDLIB_CLIB

#define LV_DEF_REFR_PERIOD 33
#define LV_DPI_DEF 130
#define LV_USE_OS LV_OS_NONE

#define LV_DRAW_BUF_STRIDE_ALIGN 1
#define LV_DRAW_BUF_ALIGN 4
#define LV_USE_DRAW_SW 1
#define LV_DRAW_SW_COMPLEX 1
#define LV_DRAW_SW_SUPPORT_RGB565 1
#define LV_DRAW_SW_SUPPORT_RGB565_SWAPPED 1
#define LV_DRAW_SW_SUPPORT_RGB565A8 1
#define LV_DRAW_SW_SUPPORT_RGB888 1
#define LV_DRAW_SW_SUPPORT_XRGB8888 1
#define LV_DRAW_SW_SUPPORT_ARGB8888 1
#define LV_DRAW_SW_SUPPORT_ARGB8888_PREMULTIPLIED 1
#define LV_DRAW_SW_SUPPORT_L8 1
#define LV_DRAW_SW_SUPPORT_AL88 1
#define LV_DRAW_SW_SUPPORT_A8 1
#define LV_DRAW_SW_SUPPORT_I1 1

#define LV_CACHE_DEF_SIZE 0
#define LV_IMAGE_HEADER_CACHE_DEF_CNT 0

#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_WARN
#define LV_LOG_PRINTF 1

#define LV_USE_ASSERT_NULL 1
#define LV_USE_ASSERT_MALLOC 1
#define LV_USE_ASSERT_STYLE 1

#define LV_FONT_MONTSERRAT_14 1
#define LV_FONT_DEFAULT &lv_font_montserrat_14
#define LV_FONT_FMT_TXT_LARGE 1
#define LV_TXT_ENC LV_TXT_ENC_UTF8
#define LV_TXT_BREAK_CHARS " ,.;:-_)}"

#define LV_USE_FLEX 1
#define LV_USE_GRID 1
#define LV_USE_THEME_DEFAULT 1
#define LV_USE_THEME_SIMPLE 1

#define LV_USE_LODEPNG 1
#define LV_USE_SNAPSHOT 1
#define LV_USE_GIF 0          /* el firmware trae su propio gifdec.c */

/* --- Driver de ventana (solo simulador) --- */
#define LV_USE_SDL 1
#define LV_SDL_INCLUDE_PATH <SDL2/SDL.h>
#define LV_SDL_RENDER_MODE LV_DISPLAY_RENDER_MODE_DIRECT
#define LV_SDL_BUF_COUNT 1
#define LV_SDL_ACCELERATED 1
#define LV_SDL_FULLSCREEN 0
#define LV_SDL_DIRECT_EXIT 1
#define LV_SDL_MOUSEWHEEL_MODE LV_SDL_MOUSEWHEEL_MODE_ENCODER

#define LV_BUILD_EXAMPLES 0
#define LV_BUILD_DEMOS 0

#endif /* LV_CONF_H */
