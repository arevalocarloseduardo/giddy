#pragma once
#include <stdarg.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ESP_LOG_NONE,
    ESP_LOG_ERROR,
    ESP_LOG_WARN,
    ESP_LOG_INFO,
    ESP_LOG_DEBUG,
    ESP_LOG_VERBOSE,
} esp_log_level_t;

void sim_log_write(esp_log_level_t level, const char* tag, const char* fmt, ...)
    __attribute__((format(printf, 3, 4)));
void sim_log_set_level(esp_log_level_t level);

#define ESP_LOGE(tag, ...) sim_log_write(ESP_LOG_ERROR, tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) sim_log_write(ESP_LOG_WARN, tag, __VA_ARGS__)
#define ESP_LOGI(tag, ...) sim_log_write(ESP_LOG_INFO, tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) sim_log_write(ESP_LOG_DEBUG, tag, __VA_ARGS__)
#define ESP_LOGV(tag, ...) sim_log_write(ESP_LOG_VERBOSE, tag, __VA_ARGS__)

#define ESP_LOG_BUFFER_HEX(tag, buf, len) ((void)0)

#ifdef __cplusplus
}
#endif
