#include "giddy_motion.h"

#include <algorithm>
#include <cmath>

#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace {
constexpr char kTag[] = "GiddyMotion";
constexpr float kGravity = 9.80665f;
constexpr float kFilterAlpha = 0.22f;
constexpr float kOrientationThreshold = 5.8f;
constexpr int kStableSamples = 5;
constexpr int64_t kShakeCooldownUs = 2000000;
}  // namespace

GiddyMotion::GiddyMotion(i2c_master_bus_handle_t bus,
                         OrientationCallback orientation_callback,
                         ShakeCallback shake_callback)
    : bus_(bus),
      orientation_callback_(std::move(orientation_callback)),
      shake_callback_(std::move(shake_callback)) {}

bool GiddyMotion::Start() {
    esp_err_t err = qmi8658_init(&imu_, bus_, QMI8658_ADDRESS_HIGH);
    if (err != ESP_OK) {
        ESP_LOGE(kTag, "QMI8658 initialization failed: %s", esp_err_to_name(err));
        return false;
    }

    qmi8658_set_accel_range(&imu_, QMI8658_ACCEL_RANGE_8G);
    qmi8658_set_accel_odr(&imu_, QMI8658_ACCEL_ODR_125HZ);
    qmi8658_set_gyro_range(&imu_, QMI8658_GYRO_RANGE_512DPS);
    qmi8658_set_gyro_odr(&imu_, QMI8658_GYRO_ODR_125HZ);
    qmi8658_set_accel_unit_mps2(&imu_, true);
    qmi8658_set_gyro_unit_rads(&imu_, true);

    if (xTaskCreate(MotionTask, "giddy_motion", 4096, this, 4, nullptr) != pdPASS) {
        ESP_LOGE(kTag, "Could not create motion task");
        return false;
    }

    ESP_LOGI(kTag, "QMI8658 active: auto-rotate and shake-to-wake enabled");
    return true;
}

void GiddyMotion::MotionTask(void* arg) {
    static_cast<GiddyMotion*>(arg)->Run();
    vTaskDelete(nullptr);
}

int GiddyMotion::ClassifyOrientation(float x, float y, float z) const {
    const float in_plane = std::sqrt(x * x + y * y);
    if (in_plane < kOrientationThreshold || std::fabs(z) > in_plane * 1.15f) {
        return -1;
    }

    if (std::fabs(x) > std::fabs(y)) {
        return x > 0.0f ? 270 : 90;
    }
    return y > 0.0f ? 0 : 180;
}

void GiddyMotion::Run() {
    bool filter_ready = false;
    float filtered_x = 0.0f;
    float filtered_y = 0.0f;
    float filtered_z = 0.0f;
    float previous_x = 0.0f;
    float previous_y = 0.0f;
    float previous_z = 0.0f;
    int candidate_orientation = -1;
    int stable_count = 0;
    int applied_orientation = -1;
    int shake_score = 0;
    int64_t last_shake_us = 0;

    while (true) {
        bool ready = false;
        if (qmi8658_is_data_ready(&imu_, &ready) != ESP_OK || !ready) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        qmi8658_data_t data{};
        if (qmi8658_read_sensor_data(&imu_, &data) != ESP_OK) {
            vTaskDelay(pdMS_TO_TICKS(40));
            continue;
        }

        if (!filter_ready) {
            filtered_x = previous_x = data.accelX;
            filtered_y = previous_y = data.accelY;
            filtered_z = previous_z = data.accelZ;
            filter_ready = true;
        } else {
            filtered_x += kFilterAlpha * (data.accelX - filtered_x);
            filtered_y += kFilterAlpha * (data.accelY - filtered_y);
            filtered_z += kFilterAlpha * (data.accelZ - filtered_z);
        }

        const int orientation = ClassifyOrientation(filtered_x, filtered_y, filtered_z);
        if (orientation >= 0) {
            if (orientation == candidate_orientation) {
                ++stable_count;
            } else {
                candidate_orientation = orientation;
                stable_count = 1;
            }
            if (stable_count >= kStableSamples && orientation != applied_orientation) {
                applied_orientation = orientation;
                orientation_callback_(orientation);
                ESP_LOGI(kTag, "Face orientation: %d degrees (%.2f, %.2f, %.2f)", orientation,
                         filtered_x, filtered_y, filtered_z);
            }
        }

        const float magnitude =
            std::sqrt(data.accelX * data.accelX + data.accelY * data.accelY +
                      data.accelZ * data.accelZ);
        const float jerk =
            std::sqrt((data.accelX - previous_x) * (data.accelX - previous_x) +
                      (data.accelY - previous_y) * (data.accelY - previous_y) +
                      (data.accelZ - previous_z) * (data.accelZ - previous_z));
        const float gravity_deviation = std::fabs(magnitude - kGravity);
        const bool movement_peak =
            (jerk > 5.0f && gravity_deviation > 2.8f) || jerk > 9.0f;
        shake_score = movement_peak ? std::min(shake_score + 1, 3)
                                    : std::max(shake_score - 1, 0);

        const int64_t now_us = esp_timer_get_time();
        if (shake_score >= 2 && now_us - last_shake_us >= kShakeCooldownUs) {
            last_shake_us = now_us;
            shake_score = 0;
            shake_callback_();
            ESP_LOGI(kTag, "Shake detected");
        }

        previous_x = data.accelX;
        previous_y = data.accelY;
        previous_z = data.accelZ;
        vTaskDelay(pdMS_TO_TICKS(40));
    }
}
