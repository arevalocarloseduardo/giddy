cmake_minimum_required(VERSION 3.20)
project(giddy_simulator LANGUAGES C CXX)

# Simulador de escritorio de la pantalla de Giddy.
# Compila el MISMO lcd_display.cc que va a la placa, con LVGL 9.5 + SDL2,
# y reemplaza ESP-IDF por stubs chiquitos (compat/).

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

get_filename_component(FW_DIR "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
set(MAIN_DIR  "${FW_DIR}/main")
set(LVGL_DIR  "${FW_DIR}/managed_components/lvgl__lvgl")
set(FONTS_DIR "${FW_DIR}/managed_components/78__xiaozhi-fonts")

if(NOT EXISTS "${LVGL_DIR}/lvgl.h")
    message(FATAL_ERROR
        "No encuentro LVGL en ${LVGL_DIR}. Compilá el firmware una vez (idf.py build) "
        "para que ESP-IDF baje managed_components/, o cloná lvgl v9.5.0 ahí.")
endif()

# Fuentes built-in: las mismas que elige main/CMakeLists.txt para la Touch-LCD-1.54
set(SIM_TEXT_FONT "font_noto_sans_basic_16_4" CACHE STRING "BUILTIN_TEXT_FONT del firmware")
set(SIM_ICON_FONT "font_material_symbols_20_4" CACHE STRING "BUILTIN_ICON_FONT del firmware")

# Dónde están los GIFs del avatar (se prueban en orden en tiempo de ejecución)
set(SIM_EMOJI_DIRS
    "${FW_DIR}/custom_emoji/robot-pro_240"
    "${FW_DIR}/../avatar/robot-pro_240")
string(REPLACE ";" "|" SIM_EMOJI_DIRS_STR "${SIM_EMOJI_DIRS}")

# ---------- SDL2 ----------
find_package(SDL2 CONFIG QUIET)
if(TARGET SDL2::SDL2)
    set(SIM_SDL SDL2::SDL2)
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(SDL2 REQUIRED IMPORTED_TARGET sdl2)
    set(SIM_SDL PkgConfig::SDL2)
endif()

# ---------- LVGL (el mismo árbol que usa el firmware) ----------
set(LV_BUILD_CONF_PATH "${CMAKE_CURRENT_SOURCE_DIR}/lv_conf.h" CACHE PATH "" FORCE)
set(CONFIG_LV_BUILD_DEMOS OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_USE_THORVG_INTERNAL OFF CACHE BOOL "" FORCE)
add_compile_definitions(LV_CONF_PATH="${CMAKE_CURRENT_SOURCE_DIR}/lv_conf.h" LV_LVGL_H_INCLUDE_SIMPLE)
add_subdirectory(${LVGL_DIR} ${CMAKE_BINARY_DIR}/lvgl EXCLUDE_FROM_ALL)
target_link_libraries(lvgl PUBLIC ${SIM_SDL})
target_compile_options(lvgl PRIVATE -w)

# ---------- Fuentes del firmware ----------
file(GLOB FONT_SOURCES "${FONTS_DIR}/src/*.c")
add_library(xiaozhi_fonts STATIC ${FONT_SOURCES})
target_include_directories(xiaozhi_fonts PUBLIC "${FONTS_DIR}/include")
target_link_libraries(xiaozhi_fonts PUBLIC lvgl)
target_compile_options(xiaozhi_fonts PRIVATE -w)

# ---------- Código de display REAL del firmware ----------
set(DISPLAY_SOURCES
    ${MAIN_DIR}/display/display.cc
    ${MAIN_DIR}/display/lcd_display.cc
    ${MAIN_DIR}/display/text_glyph.cc
    ${MAIN_DIR}/display/lvgl_display/lvgl_display.cc
    ${MAIN_DIR}/display/lvgl_display/lvgl_image.cc
    ${MAIN_DIR}/display/lvgl_display/lvgl_font.cc
    ${MAIN_DIR}/display/lvgl_display/lvgl_theme.cc
    ${MAIN_DIR}/display/lvgl_display/emoji_collection.cc
    ${MAIN_DIR}/display/lvgl_display/dynamic_glyph_cache.cc
    ${MAIN_DIR}/display/lvgl_display/gif/lvgl_gif.cc
    ${MAIN_DIR}/display/lvgl_display/gif/gifdec.c
)

add_executable(giddy_simulator
    src/main.cc
    src/sim_esp.cc
    src/sim_sounds.cc
    ${DISPLAY_SOURCES}
)

# Orden importa: compat/ ANTES que main/ para que "settings.h", "board.h",
# "application.h" resuelvan a los stubs y no al código real.
target_include_directories(giddy_simulator PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/compat
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${MAIN_DIR}
    ${MAIN_DIR}/display
    ${MAIN_DIR}/display/lvgl_display
    ${MAIN_DIR}/display/lvgl_display/gif
)

target_compile_definitions(giddy_simulator PRIVATE
    BUILTIN_TEXT_FONT=${SIM_TEXT_FONT}
    BUILTIN_ICON_FONT=${SIM_ICON_FONT}
    SIM_EMOJI_DIRS="${SIM_EMOJI_DIRS_STR}"
)
target_compile_options(giddy_simulator PRIVATE
    -Wall -Wno-format -Wno-unused-variable -Wno-unused-function -Wno-missing-field-initializers)
target_link_libraries(giddy_simulator PRIVATE lvgl xiaozhi_fonts ${SIM_SDL})
