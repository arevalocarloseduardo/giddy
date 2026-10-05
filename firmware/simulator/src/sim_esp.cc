// Implementación de los stubs de ESP-IDF para el simulador.
// Todo corre en un solo hilo (el de LVGL), así que los locks son no-op y
// los esp_timer se mapean a lv_timer.

#include <lvgl.h>
#include <SDL2/SDL.h>

#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>

#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lvgl_port.h"
#include "esp_pm.h"
#include "esp_psram.h"
#include "esp_timer.h"
#include "settings.h"

// ---------------- esp_err ----------------
extern "C" const char* esp_err_to_name(esp_err_t code) {
    switch (code) {
        case ESP_OK: return "ESP_OK";
        case ESP_FAIL: return "ESP_FAIL";
        case ESP_ERR_NOT_SUPPORTED: return "ESP_ERR_NOT_SUPPORTED";
        case ESP_ERR_INVALID_ARG: return "ESP_ERR_INVALID_ARG";
        default: return "ESP_ERR_UNKNOWN";
    }
}

// ---------------- esp_log ----------------
static esp_log_level_t s_log_level = ESP_LOG_INFO;

extern "C" void sim_log_set_level(esp_log_level_t level) { s_log_level = level; }

extern "C" void sim_log_write(esp_log_level_t level, const char* tag, const char* fmt, ...) {
    if (level > s_log_level) return;
    static const char letters[] = {'?', 'E', 'W', 'I', 'D', 'V'};
    fprintf(stderr, "%c (%u) %s: ", letters[level], (unsigned)SDL_GetTicks(), tag);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
}

// ---------------- heap_caps ----------------
extern "C" void* heap_caps_malloc(size_t size, uint32_t) { return malloc(size); }
extern "C" void* heap_caps_calloc(size_t n, size_t size, uint32_t) { return calloc(n, size); }
extern "C" void* heap_caps_realloc(void* p, size_t size, uint32_t) { return realloc(p, size); }
extern "C" void* heap_caps_aligned_alloc(size_t alignment, size_t size, uint32_t) {
    void* p = nullptr;
    if (alignment < sizeof(void*)) alignment = sizeof(void*);
    if (posix_memalign(&p, alignment, size) != 0) return nullptr;
    return p;
}
extern "C" void heap_caps_free(void* p) { free(p); }
// La placa tiene 8 MB de PSRAM: lo declaramos para que el código tome las
// mismas decisiones (ej. dónde guarda los glifos).
extern "C" size_t heap_caps_get_total_size(uint32_t caps) {
    return (caps & MALLOC_CAP_SPIRAM) ? 8u * 1024 * 1024 : 512u * 1024;
}
extern "C" size_t heap_caps_get_free_size(uint32_t caps) { return heap_caps_get_total_size(caps) / 2; }
extern "C" size_t heap_caps_get_largest_free_block(uint32_t caps) { return heap_caps_get_free_size(caps); }

extern "C" size_t esp_psram_get_size(void) { return 8u * 1024 * 1024; }

// ---------------- esp_pm ----------------
extern "C" esp_err_t esp_pm_lock_create(esp_pm_lock_type_t, int, const char*, esp_pm_lock_handle_t* out) {
    if (out) *out = nullptr;
    return ESP_ERR_NOT_SUPPORTED;  // igual que una placa sin power management
}
extern "C" esp_err_t esp_pm_lock_acquire(esp_pm_lock_handle_t) { return ESP_OK; }
extern "C" esp_err_t esp_pm_lock_release(esp_pm_lock_handle_t) { return ESP_OK; }
extern "C" esp_err_t esp_pm_lock_delete(esp_pm_lock_handle_t) { return ESP_OK; }

// ---------------- esp_timer sobre lv_timer ----------------
struct esp_timer {
    esp_timer_cb_t cb;
    void* arg;
    lv_timer_t* lv;
    bool periodic;
};

static void sim_timer_trampoline(lv_timer_t* t) {
    auto* h = static_cast<esp_timer*>(lv_timer_get_user_data(t));
    if (!h->periodic) {
        h->lv = nullptr;  // LVGL lo borra solo al agotar repeat_count
    }
    if (h->cb) h->cb(h->arg);
}

extern "C" esp_err_t esp_timer_create(const esp_timer_create_args_t* args, esp_timer_handle_t* out) {
    if (!args || !out) return ESP_ERR_INVALID_ARG;
    auto* h = new esp_timer{args->callback, args->arg, nullptr, false};
    *out = h;
    return ESP_OK;
}

static esp_err_t sim_timer_start(esp_timer_handle_t h, uint64_t us, bool periodic) {
    if (!h) return ESP_ERR_INVALID_ARG;
    if (h->lv) {
        lv_timer_delete(h->lv);
        h->lv = nullptr;
    }
    uint32_t ms = (uint32_t)(us / 1000);
    if (ms == 0) ms = 1;
    h->periodic = periodic;
    h->lv = lv_timer_create(sim_timer_trampoline, ms, h);
    if (!periodic) lv_timer_set_repeat_count(h->lv, 1);
    return ESP_OK;
}

extern "C" esp_err_t esp_timer_start_once(esp_timer_handle_t h, uint64_t us) {
    return sim_timer_start(h, us, false);
}
extern "C" esp_err_t esp_timer_start_periodic(esp_timer_handle_t h, uint64_t us) {
    return sim_timer_start(h, us, true);
}
extern "C" esp_err_t esp_timer_stop(esp_timer_handle_t h) {
    if (!h) return ESP_ERR_INVALID_ARG;
    if (!h->lv) return ESP_ERR_INVALID_STATE;
    lv_timer_delete(h->lv);
    h->lv = nullptr;
    return ESP_OK;
}
extern "C" esp_err_t esp_timer_delete(esp_timer_handle_t h) {
    if (!h) return ESP_ERR_INVALID_ARG;
    esp_timer_stop(h);
    delete h;
    return ESP_OK;
}
extern "C" bool esp_timer_is_active(esp_timer_handle_t h) { return h && h->lv; }
extern "C" int64_t esp_timer_get_time(void) { return (int64_t)SDL_GetTicks64() * 1000; }

// ---------------- esp_lcd / lvgl_port (no-op) ----------------
extern "C" esp_err_t esp_lcd_panel_io_del(esp_lcd_panel_io_handle_t) { return ESP_OK; }
extern "C" esp_err_t esp_lcd_panel_draw_bitmap(esp_lcd_panel_handle_t, int, int, int, int, const void*) {
    return ESP_OK;
}
extern "C" esp_err_t esp_lcd_panel_disp_on_off(esp_lcd_panel_handle_t, bool) { return ESP_OK; }
extern "C" esp_err_t esp_lcd_panel_del(esp_lcd_panel_handle_t) { return ESP_OK; }

// La pantalla SDL que main.cc crea antes de construir el display. Así el
// constructor real de SpiLcdDisplay "agrega" la pantalla igual que en la placa.
static lv_display_t* s_sim_display = nullptr;
void sim_set_lvgl_display(lv_display_t* disp) { s_sim_display = disp; }

extern "C" esp_err_t lvgl_port_init(const lvgl_port_cfg_t*) { return ESP_OK; }
extern "C" lv_display_t* lvgl_port_add_disp(const lvgl_port_display_cfg_t*) { return s_sim_display; }
extern "C" lv_display_t* lvgl_port_add_disp_rgb(const lvgl_port_display_cfg_t*,
                                                const lvgl_port_display_rgb_cfg_t*) {
    return nullptr;
}
extern "C" lv_display_t* lvgl_port_add_disp_dsi(const lvgl_port_display_cfg_t*,
                                                const lvgl_port_display_dsi_cfg_t*) {
    return nullptr;
}
extern "C" bool lvgl_port_lock(uint32_t) { return true; }
extern "C" void lvgl_port_unlock(void) {}

// ---------------- Settings (NVS) en memoria ----------------
static std::map<std::string, std::map<std::string, std::string>> s_nvs;

Settings::Settings(const std::string& ns, bool read_write) : ns_(ns), read_write_(read_write) {}
Settings::~Settings() {}

std::string Settings::GetString(const std::string& key, const std::string& def) {
    auto& m = s_nvs[ns_];
    auto it = m.find(key);
    return it == m.end() ? def : it->second;
}
void Settings::SetString(const std::string& key, const std::string& value) { s_nvs[ns_][key] = value; }
int32_t Settings::GetInt(const std::string& key, int32_t def) {
    auto v = GetString(key, "");
    return v.empty() ? def : (int32_t)strtol(v.c_str(), nullptr, 10);
}
void Settings::SetInt(const std::string& key, int32_t value) { SetString(key, std::to_string(value)); }
bool Settings::GetBool(const std::string& key, bool def) { return GetInt(key, def ? 1 : 0) != 0; }
void Settings::SetBool(const std::string& key, bool value) { SetInt(key, value ? 1 : 0); }
void Settings::EraseKey(const std::string& key) { s_nvs[ns_].erase(key); }
void Settings::EraseAll() { s_nvs[ns_].clear(); }
