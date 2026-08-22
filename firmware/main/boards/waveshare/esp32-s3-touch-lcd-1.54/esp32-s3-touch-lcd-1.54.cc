#include "application.h"
#include "button.h"
#include "codecs/box_audio_codec.h"
#include "config.h"
#include "giddy_display.h"
#include "giddy_motion.h"
#include "mcp_server.h"
#include "system_reset.h"
#include "wifi_board.h"

#include <driver/i2c_master.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_log.h>
#include <esp_heap_caps.h>
#include <esp_flash.h>
#include <esp_sleep.h>
#include <wifi_station.h>
#include "i2c_device.h"

#include <esp_timer.h>

#include "assets/lang_config.h"
#include "power_save_timer.h"

#include <esp_lcd_touch_cst816s.h>
#include <esp_lvgl_port.h>
#include "driver/gpio.h"

#include "iot_button.h"

#include "esp_ota_ops.h"
#include "power_manager.h"

#include <atomic>
#include <cstdio>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define TAG "waveshare_esp32_s3_touch_lcd_1_54"

class CustomButton : public Button {
public:
    explicit CustomButton(gpio_num_t gpio_num, uint16_t long_press_time = 0)
        : Button(gpio_num, false, long_press_time) {}

    void OnPressDownDel(void) {
        if (button_handle_ == nullptr) {
            return;
        }
        on_press_down_ = NULL;
        iot_button_unregister_cb(button_handle_, BUTTON_PRESS_DOWN, nullptr);
    }
    void OnPressUpDel(void) {
        if (button_handle_ == nullptr) {
            return;
        }
        on_press_up_ = NULL;
        iot_button_unregister_cb(button_handle_, BUTTON_PRESS_UP, nullptr);
    }
};

class CustomBoard : public WifiBoard {
private:
    CustomButton pwr_button_;
    CustomButton volume_up_button_;
    CustomButton volume_down_button_;
    i2c_master_bus_handle_t i2c_bus_;
    GiddyDisplay* display_ = nullptr;
    PowerManager* power_manager_ = nullptr;
    PowerSaveTimer* power_save_timer_ = nullptr;
    GiddyMotion* motion_ = nullptr;
    std::atomic_bool shutting_down_{false};
    bool power_button_armed_ = false;

    static void ShutdownTask(void* arg) {
        auto self = static_cast<CustomBoard*>(arg);
        vTaskDelay(pdMS_TO_TICKS(1350));
        self->GetBacklight()->SetBrightness(12);
        vTaskDelay(pdMS_TO_TICKS(650));
        self->GetBacklight()->SetBrightness(0);
        vTaskDelay(pdMS_TO_TICKS(180));
        self->power_manager_->PowerOff();

        // Battery power is now cut. USB can still supply the ESP32, so enter deep
        // sleep as the equivalent of off and use PWR (GPIO 5, active low) to wake.
        while (gpio_get_level(PWR_BUTTON_GPIO) == 0) {
            vTaskDelay(pdMS_TO_TICKS(25));
        }
        ESP_ERROR_CHECK(esp_sleep_enable_ext0_wakeup(PWR_BUTTON_GPIO, 0));
        esp_deep_sleep_start();
    }

    void GracefulPowerOff() {
        if (power_manager_ == nullptr || shutting_down_.exchange(true)) {
            return;
        }

        ESP_LOGI(TAG, "Starting Giddy farewell sequence");
        if (display_ != nullptr) {
            display_->PlayFarewellSequence();
        }
        if (xTaskCreate(ShutdownTask, "giddy_shutdown", 3072, this, 4, nullptr) != pdPASS) {
            ESP_LOGE(TAG, "Could not create shutdown task; powering off immediately");
            power_manager_->PowerOff();
        }
    }

    void InitializePowerManager() {
        power_manager_ = new PowerManager(BATTERY_CHARGING_PIN, BATTERY_ADC_PIN, BATTERY_EN_PIN);
        power_manager_->PowerON();
    }

    void InitializePowerSaveTimer() {
        power_save_timer_ = new PowerSaveTimer(-1, 60, 300);
        power_save_timer_->OnEnterSleepMode([this]() {
            display_->SetChatMessage("system", "");
            display_->PlaySleepSequence();
            GetBacklight()->SetBrightness(20);
        });
        power_save_timer_->OnExitSleepMode([this]() {
            display_->SetChatMessage("system", "");
            GetBacklight()->RestoreBrightness();
            display_->PlayWakeSequence();
        });
        power_save_timer_->OnShutdownRequest([this]() { GracefulPowerOff(); });
        power_save_timer_->SetEnabled(true);
    }

    void InitializeI2c() {
        // Initialize I2C peripheral
        i2c_master_bus_config_t i2c_bus_cfg = {
            .i2c_port = (i2c_port_t)0,
            .sda_io_num = AUDIO_CODEC_I2C_SDA_PIN,
            .scl_io_num = AUDIO_CODEC_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags =
                {
                    .enable_internal_pullup = 1,
                },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_bus_cfg, &i2c_bus_));
    }

    void InitializeMotion() {
        motion_ = new GiddyMotion(
            i2c_bus_, [this](int degrees) { display_->SetFaceRotation(degrees); },
            [this]() {
                if (!shutting_down_) {
                    power_save_timer_->WakeUp();
                    auto& app = Application::GetInstance();
                    if (app.GetDeviceState() == kDeviceStateIdle) {
                        display_->SetPowerSaveMode(false);
                        app.WakeWordInvoke("Giddy");
                    }
                }
            });
        if (!motion_->Start()) {
            ESP_LOGW(TAG, "Motion features are unavailable");
        }
    }

    void InitializeSpi() {
        ESP_LOGI(TAG, "Initialize QSPI bus");
        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = DISPLAY_MOSI_PIN;
        buscfg.miso_io_num = DISPLAY_MISO_PIN;
        buscfg.sclk_io_num = DISPLAY_CLK_PIN;
        buscfg.quadwp_io_num = GPIO_NUM_NC;
        buscfg.quadhd_io_num = GPIO_NUM_NC;
        buscfg.max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &buscfg, SPI_DMA_CH_AUTO));
    }

    void InitializeTouch() {
        esp_err_t ret = ESP_OK;
        esp_lcd_touch_handle_t touch_handle;

        esp_lcd_panel_io_handle_t tp_io_handle = NULL;

        esp_lcd_panel_io_i2c_config_t tp_io_config = {};
        tp_io_config.dev_addr = ESP_LCD_TOUCH_IO_I2C_CST816S_ADDRESS;
        tp_io_config.scl_speed_hz = 100000;
        tp_io_config.control_phase_bytes = 1;
        tp_io_config.dc_bit_offset = 0;
        tp_io_config.lcd_cmd_bits = 8;
        tp_io_config.lcd_param_bits = 0;
        tp_io_config.flags.disable_control_phase = 1;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c(i2c_bus_, &tp_io_config, &tp_io_handle));

        esp_lcd_touch_config_t tp_cfg = {
            .x_max = DISPLAY_WIDTH,
            .y_max = DISPLAY_HEIGHT,
            .rst_gpio_num = TOOUCH_RST_PIN,
            .int_gpio_num = TOOUCH_INT_PIN,
            .flags =
                {
                    .swap_xy = 0,
                    .mirror_x = 0,
                    .mirror_y = 0,
                },
        };
        ESP_LOGI(TAG, "Initialize touch controller CST816");
        ret = esp_lcd_touch_new_i2c_cst816s(tp_io_handle, &tp_cfg, &touch_handle);
        if (ret == ESP_OK) {
            const lvgl_port_touch_cfg_t touch_cfg = {
                .disp = lv_display_get_default(),
                .handle = touch_handle,
            };
            lvgl_port_add_touch(&touch_cfg);
            ESP_LOGI(TAG, "Touch panel initialized successfully");
        }
    }

    void InitializeLcdDisplay() {
        esp_lcd_panel_io_handle_t panel_io = nullptr;
        esp_lcd_panel_handle_t panel = nullptr;
        // 液晶屏控制IO初始化
        ESP_LOGI(TAG, "Install panel IO");
        esp_lcd_panel_io_spi_config_t io_config = {};
        io_config.cs_gpio_num = DISPLAY_CS_PIN;
        io_config.dc_gpio_num = DISPLAY_DC_PIN;
        io_config.spi_mode = DISPLAY_SPI_MODE;
        io_config.pclk_hz = 40 * 1000 * 1000;
        io_config.trans_queue_depth = 10;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI3_HOST, &io_config, &panel_io));

        // 初始化液晶屏驱动芯片
        ESP_LOGI(TAG, "Install LCD driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = DISPLAY_RGB_ORDER;
        panel_config.bits_per_pixel = 16;

        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(panel_io, &panel_config, &panel));

        esp_lcd_panel_reset(panel);

        esp_lcd_panel_init(panel);
        esp_lcd_panel_invert_color(panel, DISPLAY_INVERT_COLOR);
        esp_lcd_panel_swap_xy(panel, DISPLAY_SWAP_XY);
        esp_lcd_panel_mirror(panel, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);

        display_ =
            new GiddyDisplay(panel_io, panel, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_OFFSET_X,
                             DISPLAY_OFFSET_Y, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y, DISPLAY_SWAP_XY);
    }

    void ArmPowerButton() {
        if (power_button_armed_) {
            return;
        }
        power_button_armed_ = true;

        pwr_button_.OnClick([this]() {
            if (shutting_down_) {
                return;
            }
            power_save_timer_->WakeUp();
            auto& app = Application::GetInstance();
            const auto state = app.GetDeviceState();
            app.ToggleChatState();
            display_->ShowNotification(state == kDeviceStateIdle ? "Te escucho" : "Listo", 900);
            ESP_LOGI(TAG, "PWR short press: toggle conversation");
        });
        pwr_button_.OnLongPress([this]() {
            ESP_LOGI(TAG, "PWR long press: power off");
            GracefulPowerOff();
        });
        ESP_LOGI(TAG, "PWR button armed");
    }

    void InitializeButtons() {
        // When starting from battery, PWR can still be held down. Arm it on the
        // initial release so that powering on cannot immediately power off again.
        // USB startup arrives with the button released and can be armed now.
        if (gpio_get_level(PWR_BUTTON_GPIO) == 0) {
            pwr_button_.OnPressUp([this]() {
                pwr_button_.OnPressUpDel();
                ArmPowerButton();
            });
        } else {
            ArmPowerButton();
        }

        volume_up_button_.OnClick([this]() {
            if (shutting_down_) {
                return;
            }
            power_save_timer_->WakeUp();
            auto codec = Board::GetInstance().GetAudioCodec();
            auto volume = codec->output_volume() + 10;
            if (volume > 100) {
                volume = 100;
            }
            codec->SetOutputVolume(volume);
            const auto message = std::string("Volumen ") + std::to_string(volume) + "%";
            display_->ShowNotification(message.c_str(), 1200);
            ESP_LOGI(TAG, "PLUS button: volume %d", volume);
        });

        volume_up_button_.OnLongPress([this]() {
            if (shutting_down_) {
                return;
            }
            power_save_timer_->WakeUp();
            Board::GetInstance().GetAudioCodec()->SetOutputVolume(100);
            display_->ShowNotification("Volumen 100%", 1200);
            ESP_LOGI(TAG, "PLUS long press: maximum volume");
        });

        volume_down_button_.OnClick([this]() {
            if (shutting_down_) {
                return;
            }
            power_save_timer_->WakeUp();
            auto codec = Board::GetInstance().GetAudioCodec();
            auto volume = codec->output_volume() - 10;
            if (volume < 0) {
                volume = 0;
            }
            codec->SetOutputVolume(volume);
            const auto message = std::string("Volumen ") + std::to_string(volume) + "%";
            display_->ShowNotification(message.c_str(), 1200);
            ESP_LOGI(TAG, "BOOT button: volume %d", volume);
        });

        volume_down_button_.OnLongPress([this]() {
            if (shutting_down_) {
                return;
            }
            power_save_timer_->WakeUp();
            Board::GetInstance().GetAudioCodec()->SetOutputVolume(0);
            display_->ShowNotification("Silencio", 1200);
            ESP_LOGI(TAG, "BOOT long press: mute");
        });
    }

    // 初始化工具
    void InitializeTools() {
        auto& mcp_server = McpServer::GetInstance();
        mcp_server.AddTool(
            "self.system.get_memory",
            "Get live internal RAM, PSRAM and flash usage in bytes. Use this tool before "
            "answering how much memory is currently free.",
            PropertyList(), [](const PropertyList& properties) -> ReturnValue {
                const size_t internal_total = heap_caps_get_total_size(MALLOC_CAP_INTERNAL);
                const size_t internal_free = heap_caps_get_free_size(MALLOC_CAP_INTERNAL);
                const size_t internal_largest =
                    heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL);
                const size_t psram_total = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
                const size_t psram_free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
                const size_t psram_largest =
                    heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
                uint32_t flash_total = 0;
                esp_flash_get_size(nullptr, &flash_total);
                char json[384];
                std::snprintf(
                    json, sizeof(json),
                    "{\"internal_ram\":{\"total\":%u,\"free\":%u,\"largest_block\":%u},"
                    "\"psram\":{\"total\":%u,\"free\":%u,\"largest_block\":%u},"
                    "\"flash\":{\"total\":%u}}",
                    static_cast<unsigned>(internal_total), static_cast<unsigned>(internal_free),
                    static_cast<unsigned>(internal_largest), static_cast<unsigned>(psram_total),
                    static_cast<unsigned>(psram_free), static_cast<unsigned>(psram_largest),
                    static_cast<unsigned>(flash_total));
                return std::string(json);
            });
        mcp_server.AddTool("self.system.reconfigure_wifi",
                           "Reboot the device and enter WiFi configuration mode.\n"
                           "**CAUTION** You must ask the user to confirm this action.",
                           PropertyList(), [this](const PropertyList& properties) {
                               EnterWifiConfigMode();
                               return true;
                           });
    }

public:
    CustomBoard()
        : pwr_button_(PWR_BUTTON_GPIO, 1800),
          volume_up_button_(VOLUME_UP_BUTTON_GPIO),
          volume_down_button_(VOLUME_DOWN_BUTTON_GPIO) {
        InitializePowerManager();
        InitializePowerSaveTimer();
        InitializeI2c();
        InitializeSpi();
        InitializeLcdDisplay();
        InitializeTouch();
        InitializeMotion();
        InitializeButtons();
        InitializeTools();
        GetBacklight()->RestoreBrightness();
    }

    virtual AudioCodec* GetAudioCodec() override {
        static BoxAudioCodec audio_codec(
            i2c_bus_, AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE, AUDIO_I2S_GPIO_MCLK,
            AUDIO_I2S_GPIO_BCLK, AUDIO_I2S_GPIO_WS, AUDIO_I2S_GPIO_DOUT, AUDIO_I2S_GPIO_DIN,
            AUDIO_CODEC_PA_PIN, AUDIO_CODEC_ES8311_ADDR, AUDIO_CODEC_ES7210_ADDR, true);
        return &audio_codec;
    }

    virtual Display* GetDisplay() override { return display_; }

    virtual Backlight* GetBacklight() override {
        static PwmBacklight backlight(DISPLAY_BACKLIGHT_PIN, DISPLAY_BACKLIGHT_OUTPUT_INVERT);
        return &backlight;
    }

    virtual bool GetBatteryLevel(int& level, bool& charging, bool& discharging) override {
        static bool last_discharging = false;
        charging = power_manager_->IsCharging();
        discharging = power_manager_->IsDischarging();
        if (discharging != last_discharging) {
            power_save_timer_->SetEnabled(discharging);
            last_discharging = discharging;
        }

        level = power_manager_->GetBatteryLevel();
        return true;
    }

    virtual void SetPowerSaveLevel(PowerSaveLevel level) override {
        if (level != PowerSaveLevel::LOW_POWER) {
            power_save_timer_->WakeUp();
        }
        WifiBoard::SetPowerSaveLevel(level);
    }
};

DECLARE_BOARD(CustomBoard);
