#include "giddy_display.h"

#include "application.h"
#include "assets.h"
#include "board.h"
#include "display/lvgl_display/lvgl_theme.h"
#include "material_symbols.h"
#include "system_info.h"

#include <algorithm>
#include <cstring>

#include <esp_log.h>

namespace {
constexpr char kTag[] = "GiddyDisplay";
constexpr uint32_t kInk = 0x17211F;
constexpr uint32_t kPaper = 0xF4F7F5;
constexpr uint32_t kSurface = 0xFFFFFF;
constexpr uint32_t kTeal = 0x087F73;
constexpr uint32_t kCoral = 0xE45C45;
constexpr uint32_t kYellow = 0xF3BA3E;
constexpr int kBootDurationMs = 2480;
constexpr int kWakeDurationMs = 1475;
constexpr int kDozingDurationMs = 1710;
constexpr int kPreviewToolbarHeight = 42;
constexpr int kPreviewAvailableHeight = 194;
constexpr int kPreviewInteractionDurationMs = 30000;
}  // namespace

GiddyDisplay::GiddyDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel,
                           int width, int height, int offset_x, int offset_y, bool mirror_x,
                           bool mirror_y, bool swap_xy)
    : SpiLcdDisplay(panel_io, panel, width, height, offset_x, offset_y, mirror_x, mirror_y,
                    swap_xy) {
    esp_timer_create_args_t moment_args = {
        .callback = OnMomentTimer,
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "giddy_moment",
        .skip_unhandled_events = true,
    };
    ESP_ERROR_CHECK(esp_timer_create(&moment_args, &moment_timer_));

    esp_timer_create_args_t idle_args = {
        .callback = OnIdleTimer,
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "giddy_idle",
        .skip_unhandled_events = true,
    };
    ESP_ERROR_CHECK(esp_timer_create(&idle_args, &idle_timer_));

    esp_timer_create_args_t feedback_args = {
        .callback = OnFeedbackTimer,
        .arg = this,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "giddy_feedback",
        .skip_unhandled_events = true,
    };
    ESP_ERROR_CHECK(esp_timer_create(&feedback_args, &feedback_timer_));
}

GiddyDisplay::~GiddyDisplay() {
    if (moment_timer_ != nullptr) {
        if (esp_timer_is_active(moment_timer_)) {
            esp_timer_stop(moment_timer_);
        }
        esp_timer_delete(moment_timer_);
    }
    if (idle_timer_ != nullptr) {
        if (esp_timer_is_active(idle_timer_)) {
            esp_timer_stop(idle_timer_);
        }
        esp_timer_delete(idle_timer_);
    }
    if (feedback_timer_ != nullptr) {
        if (esp_timer_is_active(feedback_timer_)) {
            esp_timer_stop(feedback_timer_);
        }
        esp_timer_delete(feedback_timer_);
    }
}

void GiddyDisplay::SetupUI() {
    // Create the LVGL widgets before applying custom fonts. Assets are still loaded
    // locally, before audio, WiFi and activation, so Giddy's boot does not depend on
    // any network service.
    LcdDisplay::SetupUI();

    auto& assets = Assets::GetInstance();
    if (assets.partition_valid() && !assets.Apply(false)) {
        ESP_LOGW(kTag, "Could not preload Giddy assets");
    }

    {
        DisplayLockGuard lock(this);
        auto screen = lv_screen_active();
        auto lvgl_theme = static_cast<LvglTheme*>(current_theme_);
        auto icon_font = lvgl_theme->icon_font()->font();

        home_bar_ = lv_obj_create(screen);
        lv_obj_set_size(home_bar_, 96, 42);
        lv_obj_align(home_bar_, LV_ALIGN_BOTTOM_MID, 0, -5);
        lv_obj_set_style_radius(home_bar_, 0, 0);
        lv_obj_set_style_border_width(home_bar_, 0, 0);
        lv_obj_set_style_pad_all(home_bar_, 0, 0);
        lv_obj_set_style_bg_opa(home_bar_, LV_OPA_TRANSP, 0);
        lv_obj_set_scrollbar_mode(home_bar_, LV_SCROLLBAR_MODE_OFF);
        // Keep the bottom caption lane clear. The physical top buttons remain active.
        lv_obj_add_flag(home_bar_, LV_OBJ_FLAG_HIDDEN);

        auto talk = lv_button_create(home_bar_);
        lv_obj_set_size(talk, 40, 40);
        lv_obj_align(talk, LV_ALIGN_LEFT_MID, 0, 0);
        lv_obj_set_style_radius(talk, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(talk, lv_color_hex(kTeal), 0);
        lv_obj_set_style_bg_opa(talk, LV_OPA_80, 0);
        lv_obj_add_event_cb(talk, OnTalkClicked, LV_EVENT_CLICKED, this);
        auto talk_label = lv_label_create(talk);
        lv_label_set_text(talk_label, MATERIAL_SYMBOLS_MIC);
        lv_obj_set_style_text_font(talk_label, icon_font, 0);
        lv_obj_set_style_text_color(talk_label, lv_color_hex(kSurface), 0);
        lv_obj_center(talk_label);

        auto today = lv_button_create(home_bar_);
        lv_obj_set_size(today, 40, 40);
        lv_obj_align(today, LV_ALIGN_RIGHT_MID, 0, 0);
        lv_obj_set_style_radius(today, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(today, lv_color_hex(kYellow), 0);
        lv_obj_set_style_bg_opa(today, LV_OPA_80, 0);
        lv_obj_add_event_cb(today, OnDashboardClicked, LV_EVENT_CLICKED, this);
        auto today_label = lv_label_create(today);
        lv_label_set_text(today_label, MATERIAL_SYMBOLS_CALENDAR_MONTH);
        lv_obj_set_style_text_font(today_label, icon_font, 0);
        lv_obj_set_style_text_color(today_label, lv_color_hex(kInk), 0);
        lv_obj_center(today_label);

        dashboard_ = lv_obj_create(screen);
        lv_obj_set_size(dashboard_, 240, 240);
        lv_obj_align(dashboard_, LV_ALIGN_CENTER, 0, 0);
        lv_obj_set_style_radius(dashboard_, 0, 0);
        lv_obj_set_style_border_width(dashboard_, 0, 0);
        lv_obj_set_style_pad_all(dashboard_, 0, 0);
        lv_obj_set_style_bg_color(dashboard_, lv_color_hex(kPaper), 0);
        lv_obj_set_scrollbar_mode(dashboard_, LV_SCROLLBAR_MODE_OFF);

        auto title = lv_label_create(dashboard_);
        lv_label_set_text(title, "Hoy con Giddy");
        lv_obj_set_style_text_color(title, lv_color_hex(kInk), 0);
        lv_obj_align(title, LV_ALIGN_TOP_LEFT, 10, 12);

        auto back = lv_button_create(dashboard_);
        lv_obj_set_size(back, 54, 28);
        lv_obj_align(back, LV_ALIGN_TOP_RIGHT, -8, 6);
        lv_obj_set_style_radius(back, 5, 0);
        lv_obj_set_style_bg_color(back, lv_color_hex(kInk), 0);
        lv_obj_add_event_cb(back, OnBackClicked, LV_EVENT_CLICKED, this);
        auto back_label = lv_label_create(back);
        lv_label_set_text(back_label, MATERIAL_SYMBOLS_ARROW_BACK);
        lv_obj_set_style_text_font(back_label, icon_font, 0);
        lv_obj_set_style_text_color(back_label, lv_color_hex(kSurface), 0);
        lv_obj_center(back_label);

        AddActionButton(dashboard_, "Mi agenda", "agenda", kTeal, kSurface, 10, 46);
        AddActionButton(dashboard_, "Prioridades", "priorities", kSurface, kInk, 125, 46);
        AddActionButton(dashboard_, "Foco 25 min", "focus", kYellow, kInk, 10, 130);
        AddActionButton(dashboard_, "Clima", "weather", kCoral, kSurface, 125, 130);

        auto footer = lv_label_create(dashboard_);
        lv_label_set_text(footer, "Listo para ayudarte");
        lv_obj_set_style_text_color(footer, lv_color_hex(kTeal), 0);
        lv_obj_align(footer, LV_ALIGN_BOTTOM_MID, 0, -8);
        lv_obj_add_flag(dashboard_, LV_OBJ_FLAG_HIDDEN);

        feedback_panel_ = lv_obj_create(screen);
        lv_obj_set_size(feedback_panel_, 176, 40);
        lv_obj_align(feedback_panel_, LV_ALIGN_TOP_MID, 0, 8);
        lv_obj_set_style_radius(feedback_panel_, 7, 0);
        lv_obj_set_style_border_width(feedback_panel_, 1, 0);
        lv_obj_set_style_border_color(feedback_panel_, lv_color_hex(kTeal), 0);
        lv_obj_set_style_bg_color(feedback_panel_, lv_color_hex(kInk), 0);
        lv_obj_set_style_bg_opa(feedback_panel_, LV_OPA_90, 0);
        lv_obj_set_style_pad_all(feedback_panel_, 7, 0);
        lv_obj_set_scrollbar_mode(feedback_panel_, LV_SCROLLBAR_MODE_OFF);

        feedback_label_ = lv_label_create(feedback_panel_);
        lv_obj_set_width(feedback_label_, 158);
        lv_label_set_long_mode(feedback_label_, LV_LABEL_LONG_DOT);
        lv_obj_set_style_text_align(feedback_label_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_style_text_color(feedback_label_, lv_color_hex(kSurface), 0);
        lv_label_set_text(feedback_label_, "");
        lv_obj_center(feedback_label_);
        lv_obj_add_flag(feedback_panel_, LV_OBJ_FLAG_HIDDEN);

        preview_toolbar_ = lv_obj_create(screen);
        lv_obj_set_size(preview_toolbar_, 136, kPreviewToolbarHeight);
        lv_obj_align(preview_toolbar_, LV_ALIGN_BOTTOM_MID, 0, -5);
        lv_obj_set_style_radius(preview_toolbar_, 7, 0);
        lv_obj_set_style_border_width(preview_toolbar_, 0, 0);
        lv_obj_set_style_bg_color(preview_toolbar_, lv_color_hex(kInk), 0);
        lv_obj_set_style_bg_opa(preview_toolbar_, LV_OPA_90, 0);
        lv_obj_set_style_pad_all(preview_toolbar_, 4, 0);
        lv_obj_set_style_pad_gap(preview_toolbar_, 5, 0);
        lv_obj_set_scrollbar_mode(preview_toolbar_, LV_SCROLLBAR_MODE_OFF);
        lv_obj_set_flex_flow(preview_toolbar_, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(preview_toolbar_, LV_FLEX_ALIGN_CENTER,
                              LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

        auto add_preview_button = [&](const char* symbol, const lv_font_t* font,
                                      lv_event_cb_t callback) {
            auto button = lv_button_create(preview_toolbar_);
            lv_obj_set_size(button, 36, 32);
            lv_obj_set_style_radius(button, 5, 0);
            lv_obj_set_style_border_width(button, 0, 0);
            lv_obj_set_style_bg_color(button, lv_color_hex(kSurface), 0);
            lv_obj_set_style_bg_opa(button, LV_OPA_COVER, 0);
            lv_obj_set_style_bg_color(button, lv_color_hex(kTeal), LV_STATE_PRESSED);
            lv_obj_add_event_cb(button, callback, LV_EVENT_CLICKED, this);

            auto label = lv_label_create(button);
            lv_label_set_text(label, symbol);
            if (font != nullptr) {
                lv_obj_set_style_text_font(label, font, 0);
            }
            lv_obj_set_style_text_color(label, lv_color_hex(kInk), 0);
            lv_obj_center(label);
        };

        add_preview_button(LV_SYMBOL_MINUS, nullptr, OnPreviewZoomOut);
        add_preview_button(MATERIAL_SYMBOLS_REFRESH, icon_font, OnPreviewRotate);
        add_preview_button(LV_SYMBOL_PLUS, nullptr, OnPreviewZoomIn);
        lv_obj_add_flag(preview_toolbar_, LV_OBJ_FLAG_HIDDEN);
    }

    if (!PlayBootSequence()) {
        LcdDisplay::SetEmotion("neutral");
        ArmIdleTimer();
    }
}

void GiddyDisplay::SetPreviewImage(std::unique_ptr<LvglImage> image) {
    const bool show = image != nullptr;
    LcdDisplay::SetPreviewImage(std::move(image));

    DisplayLockGuard lock(this);
    if (preview_toolbar_ == nullptr || preview_image_ == nullptr) {
        return;
    }
    if (!show || preview_image_cached_ == nullptr) {
        lv_obj_add_flag(preview_toolbar_, LV_OBJ_FLAG_HIDDEN);
        preview_fit_scale_ = 256;
        preview_scale_ = 256;
        preview_rotation_ = 0;
        return;
    }

    const auto image_description = preview_image_cached_->image_dsc();
    if (image_description == nullptr || image_description->header.w == 0 ||
        image_description->header.h == 0) {
        lv_obj_add_flag(preview_toolbar_, LV_OBJ_FLAG_HIDDEN);
        return;
    }

    const uint32_t width_scale =
        static_cast<uint32_t>(width_) * 256U / image_description->header.w;
    const uint32_t height_scale =
        kPreviewAvailableHeight * 256U / image_description->header.h;
    preview_fit_scale_ =
        std::max<uint32_t>(64, std::min<uint32_t>(width_scale, height_scale));
    preview_scale_ = preview_fit_scale_;
    preview_rotation_ = 0;

    lv_image_set_pivot(preview_image_, image_description->header.w / 2,
                       image_description->header.h / 2);
    lv_image_set_scale(preview_image_, preview_scale_);
    lv_image_set_rotation(preview_image_, preview_rotation_);
    lv_obj_align(preview_image_, LV_ALIGN_CENTER, 0, -20);
    lv_obj_move_foreground(preview_image_);
    lv_obj_remove_flag(preview_toolbar_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(preview_toolbar_);
    ExtendPreviewTimeout();
}

void GiddyDisplay::AdjustPreviewZoom(int direction) {
    if (preview_image_cached_ == nullptr || preview_image_ == nullptr) {
        return;
    }
    const uint32_t step = std::max<uint32_t>(32, preview_fit_scale_ / 4);
    const uint32_t minimum = std::max<uint32_t>(64, preview_fit_scale_ / 2);
    const uint32_t maximum = std::min<uint32_t>(1024, preview_fit_scale_ * 4);
    if (direction < 0) {
        preview_scale_ = preview_scale_ > minimum + step ? preview_scale_ - step : minimum;
    } else {
        preview_scale_ = std::min<uint32_t>(maximum, preview_scale_ + step);
    }
    lv_image_set_scale(preview_image_, preview_scale_);
    ExtendPreviewTimeout();
}

void GiddyDisplay::RotatePreview() {
    if (preview_image_cached_ == nullptr || preview_image_ == nullptr) {
        return;
    }
    preview_rotation_ = (preview_rotation_ + 900) % 3600;
    lv_image_set_rotation(preview_image_, preview_rotation_);
    ExtendPreviewTimeout();
}

void GiddyDisplay::ExtendPreviewTimeout() {
    if (preview_timer_ == nullptr) {
        return;
    }
    if (esp_timer_is_active(preview_timer_)) {
        esp_timer_stop(preview_timer_);
    }
    const esp_err_t err =
        esp_timer_start_once(preview_timer_, kPreviewInteractionDurationMs * 1000LL);
    if (err != ESP_OK) {
        ESP_LOGW(kTag, "Could not extend image preview: %s", esp_err_to_name(err));
    }
}

void GiddyDisplay::SetStatus(const char* status) {
    LcdDisplay::SetStatus(status);

    const int state = static_cast<int>(Application::GetInstance().GetDeviceState());
    bool state_changed = false;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        state_changed = state != last_visual_state_;
        last_visual_state_ = state;
    }
    if (state_changed) {
        SetActivityEmotion(ResolveActivityEmotion());
    }
}

void GiddyDisplay::SetChatMessage(const char* role, const char* content) {
    // Application::Initialize sends a board/version diagnostic immediately after
    // SetupUI. Keep the product boot cinematic clean while preserving real system
    // notices, transcripts and activation messages in every later state.
    if (Application::GetInstance().GetDeviceState() == kDeviceStateStarting && role != nullptr &&
        std::strcmp(role, "system") == 0 && content != nullptr &&
        content == SystemInfo::GetUserAgent()) {
        return;
    }
    LcdDisplay::SetChatMessage(role, content);

    DisplayLockGuard lock(this);
    ApplyFaceRotationLocked();
}

void GiddyDisplay::ShowNotification(const char* notification, int duration_ms) {
    if (notification == nullptr || feedback_panel_ == nullptr || feedback_label_ == nullptr) {
        return;
    }

    {
        DisplayLockGuard lock(this);
        lv_label_set_text(feedback_label_, notification);
        lv_obj_remove_flag(feedback_panel_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(feedback_panel_);
    }

    if (feedback_timer_ == nullptr) {
        return;
    }
    if (esp_timer_is_active(feedback_timer_)) {
        esp_timer_stop(feedback_timer_);
    }
    const int visible_ms = duration_ms > 0 ? duration_ms : 1200;
    const esp_err_t err = esp_timer_start_once(feedback_timer_, visible_ms * 1000LL);
    if (err != ESP_OK) {
        ESP_LOGW(kTag, "Could not start feedback timer: %s", esp_err_to_name(err));
    }
}

void GiddyDisplay::SetPowerSaveMode(bool on) {
    if (on) {
        PlaySleepSequence();
    } else {
        PlayWakeSequence();
    }
}

void GiddyDisplay::SetEmotion(const char* emotion) {
    if (emotion == nullptr || emotion[0] == '\0') {
        return;
    }

    if (std::strcmp(emotion, "robot_2") == 0) {
        if (PlayBootSequence()) {
            return;
        }
        SetActivityEmotion(ResolveActivityEmotion());
        return;
    }

    const bool activity_emotion =
        IsActivityEmotion(emotion) || std::strcmp(emotion, "neutral") == 0;
    const char* target = activity_emotion ? ResolveActivityEmotion() : emotion;
    bool cancel_moment = false;
    bool show_controls = false;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (farewell_active_) {
            return;
        }
        if (moment_active_ && activity_emotion) {
            moment_fallback_ = target;
            return;
        }
        if (moment_active_) {
            moment_active_ = false;
            ++moment_generation_;
            cancel_moment = true;
            show_controls = !sleeping_;
        }
    }
    if (cancel_moment && moment_timer_ != nullptr && esp_timer_is_active(moment_timer_)) {
        esp_timer_stop(moment_timer_);
    }
    if (cancel_moment) {
        SetControlsVisible(show_controls);
    }

    if (activity_emotion) {
        SetActivityEmotion(target);
    } else {
        LcdDisplay::SetEmotion(target);
    }
    ArmIdleTimer();
}

void GiddyDisplay::SetFaceRotation(int degrees) {
    const int normalized = ((degrees % 360) + 360) % 360;
    if (normalized == face_rotation_degrees_) {
        return;
    }

    DisplayLockGuard lock(this);
    face_rotation_degrees_ = normalized;
    ApplyFaceRotationLocked();
}

void GiddyDisplay::ApplyFaceRotationLocked() {
    if (emoji_box_ != nullptr) {
        lv_obj_set_style_transform_pivot_x(emoji_box_, width_ / 2, 0);
        lv_obj_set_style_transform_pivot_y(emoji_box_, height_ / 2, 0);
        lv_obj_set_style_transform_rotation(emoji_box_, face_rotation_degrees_ * 10, 0);
    }

    if (bottom_bar_ != nullptr) {
        lv_obj_update_layout(bottom_bar_);
        const int pivot_x = width_ / 2 - lv_obj_get_x(bottom_bar_);
        const int pivot_y = height_ / 2 - lv_obj_get_y(bottom_bar_);
        lv_obj_set_style_transform_pivot_x(bottom_bar_, pivot_x, 0);
        lv_obj_set_style_transform_pivot_y(bottom_bar_, pivot_y, 0);
        lv_obj_set_style_transform_rotation(bottom_bar_, face_rotation_degrees_ * 10, 0);
    }
}

bool GiddyDisplay::HasEmotion(const char* emotion) const {
    if (current_theme_ == nullptr || emotion == nullptr) {
        return false;
    }
    auto theme = static_cast<LvglTheme*>(current_theme_);
    auto collection = theme->emoji_collection();
    return collection != nullptr && collection->GetEmojiImage(emotion) != nullptr;
}

bool GiddyDisplay::StartMoment(const char* emotion, int duration_ms, const char* fallback,
                               bool controls_after) {
    if (!HasEmotion(emotion)) {
        ESP_LOGW(kTag, "Animation '%s' is not available in the assets partition", emotion);
        return false;
    }

    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        ++moment_generation_;
        moment_active_ = true;
        moment_fallback_ = fallback != nullptr ? fallback : "";
        controls_after_moment_ = controls_after;
        moment_deadline_us_ = esp_timer_get_time() + duration_ms * 1000LL;
    }
    if (moment_timer_ != nullptr && esp_timer_is_active(moment_timer_)) {
        esp_timer_stop(moment_timer_);
    }
    LcdDisplay::SetEmotion(emotion);
    if (moment_timer_ != nullptr) {
        const esp_err_t err = esp_timer_start_once(moment_timer_, duration_ms * 1000LL);
        if (err != ESP_OK) {
            ESP_LOGE(kTag, "Could not start '%s' animation timer: %s", emotion,
                     esp_err_to_name(err));
            CancelMoment();
            return false;
        }
    }
    return true;
}

bool GiddyDisplay::PlayBootSequence() {
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (boot_played_ || farewell_active_) {
            return false;
        }
        boot_played_ = true;
    }
    SetControlsVisible(false);
    if (!StartMoment("boot", kBootDurationMs, "", true)) {
        {
            std::lock_guard<std::mutex> lock(personality_mutex_);
            boot_played_ = false;
        }
        SetControlsVisible(true);
        return false;
    }
    return true;
}

void GiddyDisplay::PlaySleepSequence() {
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (farewell_active_ || sleeping_) {
            return;
        }
        sleeping_ = true;
    }
    if (idle_timer_ != nullptr && esp_timer_is_active(idle_timer_)) {
        esp_timer_stop(idle_timer_);
    }
    SetControlsVisible(false);
    if (!StartMoment("dozing", kDozingDurationMs, "sleepy", false)) {
        LcdDisplay::SetEmotion("sleepy");
    }
}

void GiddyDisplay::PlayWakeSequence() {
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (farewell_active_ || !sleeping_) {
            return;
        }
        sleeping_ = false;
    }
    SetControlsVisible(false);
    if (!StartMoment("wake", kWakeDurationMs, "", true)) {
        SetControlsVisible(true);
        SetActivityEmotion(ResolveActivityEmotion());
        ArmIdleTimer();
    }
}

void GiddyDisplay::PlayFarewellSequence() {
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        farewell_active_ = true;
        sleeping_ = false;
    }
    if (idle_timer_ != nullptr && esp_timer_is_active(idle_timer_)) {
        esp_timer_stop(idle_timer_);
    }
    if (feedback_timer_ != nullptr && esp_timer_is_active(feedback_timer_)) {
        esp_timer_stop(feedback_timer_);
    }
    HideFeedback();
    SetControlsVisible(false);
    if (!StartMoment("goodnight", 2600, "sleepy", false)) {
        LcdDisplay::SetEmotion("sleepy");
    }
}

void GiddyDisplay::FinishMoment(uint32_t generation) {
    std::string fallback;
    bool controls_after = true;
    bool should_finish = false;
    bool sleeping = false;
    bool farewell = false;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (moment_active_ && generation == moment_generation_) {
            moment_active_ = false;
            fallback = moment_fallback_;
            controls_after = controls_after_moment_;
            sleeping = sleeping_;
            farewell = farewell_active_;
            moment_deadline_us_ = 0;
            should_finish = true;
        }
    }
    if (!should_finish || farewell) {
        return;
    }

    if (fallback.empty()) {
        fallback = ResolveActivityEmotion();
    }
    if (IsActivityEmotion(fallback.c_str()) || fallback == "neutral") {
        SetActivityEmotion(fallback.c_str());
    } else {
        LcdDisplay::SetEmotion(fallback.c_str());
    }
    SetControlsVisible(controls_after && !sleeping);
    ArmIdleTimer();
}

void GiddyDisplay::CancelMoment() {
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        moment_active_ = false;
        moment_deadline_us_ = 0;
        ++moment_generation_;
    }
    if (moment_timer_ != nullptr && esp_timer_is_active(moment_timer_)) {
        esp_timer_stop(moment_timer_);
    }
}

void GiddyDisplay::SetActivityEmotion(const char* emotion) {
    if (emotion == nullptr) {
        emotion = "neutral";
    }
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        if (farewell_active_) {
            return;
        }
        if (moment_active_) {
            moment_fallback_ = emotion;
            return;
        }
    }
    LcdDisplay::SetEmotion(HasEmotion(emotion) ? emotion : "neutral");
}

const char* GiddyDisplay::ResolveActivityEmotion() const {
    switch (Application::GetInstance().GetDeviceState()) {
        case kDeviceStateListening:
            return "listening";
        case kDeviceStateSpeaking:
            return "speaking";
        case kDeviceStateStarting:
        case kDeviceStateConnecting:
        case kDeviceStateActivating:
        case kDeviceStateUpgrading:
        case kDeviceStateWifiConfiguring:
            return "connecting";
        default:
            return "neutral";
    }
}

bool GiddyDisplay::IsActivityEmotion(const char* emotion) {
    return std::strcmp(emotion, "listening") == 0 || std::strcmp(emotion, "speaking") == 0 ||
           std::strcmp(emotion, "connecting") == 0;
}

void GiddyDisplay::ArmIdleTimer() {
    bool can_arm = false;
    uint32_t sequence = 0;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        can_arm = !sleeping_ && !farewell_active_;
        sequence = idle_sequence_;
    }
    if (!can_arm || idle_timer_ == nullptr) {
        return;
    }
    if (esp_timer_is_active(idle_timer_)) {
        esp_timer_stop(idle_timer_);
    }
    const int delay_seconds = 18 + static_cast<int>(sequence % 3) * 6;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        idle_deadline_us_ = esp_timer_get_time() + delay_seconds * 1000000LL;
    }
    esp_timer_start_once(idle_timer_, delay_seconds * 1000000LL);
}

void GiddyDisplay::HandleIdleTimer() {
    bool can_play = Application::GetInstance().GetDeviceState() == kDeviceStateIdle;
    uint32_t variant = 0;
    {
        std::lock_guard<std::mutex> lock(personality_mutex_);
        can_play = can_play && !moment_active_ && !sleeping_ && !farewell_active_;
        variant = idle_sequence_++ % 3;
    }
    if (can_play) {
        static constexpr const char* kIdleMoments[] = {"curious", "winking", "happy"};
        static constexpr int kIdleDurationsMs[] = {1150, 1800, 820};
        StartMoment(kIdleMoments[variant], kIdleDurationsMs[variant], "neutral", true);
    }
    ArmIdleTimer();
}

void GiddyDisplay::OnMomentTimer(void* arg) {
    auto self = static_cast<GiddyDisplay*>(arg);
    uint32_t generation = 0;
    {
        std::lock_guard<std::mutex> lock(self->personality_mutex_);
        if (!self->moment_active_ || esp_timer_get_time() + 5000 < self->moment_deadline_us_) {
            return;
        }
        generation = self->moment_generation_;
    }
    Application::GetInstance().Schedule([self, generation]() { self->FinishMoment(generation); });
}

void GiddyDisplay::OnIdleTimer(void* arg) {
    auto self = static_cast<GiddyDisplay*>(arg);
    {
        std::lock_guard<std::mutex> lock(self->personality_mutex_);
        if (esp_timer_get_time() + 5000 < self->idle_deadline_us_) {
            return;
        }
        self->idle_deadline_us_ = 0;
    }
    Application::GetInstance().Schedule([self]() { self->HandleIdleTimer(); });
}

void GiddyDisplay::OnFeedbackTimer(void* arg) {
    auto self = static_cast<GiddyDisplay*>(arg);
    Application::GetInstance().Schedule([self]() { self->HideFeedback(); });
}

void GiddyDisplay::AddActionButton(lv_obj_t* parent, const char* label, const char* action_id,
                                   uint32_t background, uint32_t foreground, int x, int y) {
    auto button = lv_button_create(parent);
    lv_obj_set_pos(button, x, y);
    lv_obj_set_size(button, 105, 74);
    lv_obj_set_style_radius(button, 7, 0);
    lv_obj_set_style_bg_color(button, lv_color_hex(background), 0);
    lv_obj_set_style_border_width(button, background == kSurface ? 1 : 0, 0);
    lv_obj_set_style_border_color(button, lv_color_hex(0xD9DFDC), 0);
    lv_obj_add_event_cb(button, OnActionClicked, LV_EVENT_CLICKED, const_cast<char*>(action_id));

    auto text = lv_label_create(button);
    lv_label_set_text(text, label);
    lv_obj_set_width(text, 88);
    lv_obj_set_style_text_align(text, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_style_text_color(text, lv_color_hex(foreground), 0);
    lv_obj_center(text);
}

void GiddyDisplay::ShowDashboard(bool visible) {
    if (visible) {
        lv_obj_remove_flag(dashboard_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(dashboard_);
    } else {
        lv_obj_add_flag(dashboard_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(home_bar_);
    }
}

void GiddyDisplay::SetControlsVisible(bool visible) {
    (void)visible;
    DisplayLockGuard lock(this);
    if (home_bar_ == nullptr || dashboard_ == nullptr) {
        return;
    }
    lv_obj_add_flag(dashboard_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(home_bar_, LV_OBJ_FLAG_HIDDEN);
}

void GiddyDisplay::HideFeedback() {
    DisplayLockGuard lock(this);
    if (feedback_panel_ != nullptr) {
        lv_obj_add_flag(feedback_panel_, LV_OBJ_FLAG_HIDDEN);
    }
}

void GiddyDisplay::OnTalkClicked(lv_event_t*) { Application::GetInstance().ToggleChatState(); }

void GiddyDisplay::OnDashboardClicked(lv_event_t* event) {
    auto display = static_cast<GiddyDisplay*>(lv_event_get_user_data(event));
    display->ShowDashboard(true);
}

void GiddyDisplay::OnBackClicked(lv_event_t* event) {
    auto display = static_cast<GiddyDisplay*>(lv_event_get_user_data(event));
    display->ShowDashboard(false);
}

void GiddyDisplay::OnActionClicked(lv_event_t* event) {
    auto action_id = static_cast<const char*>(lv_event_get_user_data(event));
    auto display = static_cast<GiddyDisplay*>(Board::GetInstance().GetDisplay());
    display->ShowDashboard(false);
    display->ShowNotification("Preparando...");
    display->SetEmotion("thinking");
    Application::GetInstance().RunQuickAction(action_id);
}

void GiddyDisplay::OnPreviewZoomOut(lv_event_t* event) {
    auto display = static_cast<GiddyDisplay*>(lv_event_get_user_data(event));
    display->AdjustPreviewZoom(-1);
}

void GiddyDisplay::OnPreviewRotate(lv_event_t* event) {
    auto display = static_cast<GiddyDisplay*>(lv_event_get_user_data(event));
    display->RotatePreview();
}

void GiddyDisplay::OnPreviewZoomIn(lv_event_t* event) {
    auto display = static_cast<GiddyDisplay*>(lv_event_get_user_data(event));
    display->AdjustPreviewZoom(1);
}
