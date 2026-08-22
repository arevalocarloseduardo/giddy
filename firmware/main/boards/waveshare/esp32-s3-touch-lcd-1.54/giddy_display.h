#ifndef GIDDY_DISPLAY_H
#define GIDDY_DISPLAY_H

#include "display/lcd_display.h"

#include <cstdint>
#include <mutex>
#include <string>

#include <esp_timer.h>

class GiddyDisplay : public SpiLcdDisplay {
public:
    GiddyDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel, int width,
                 int height, int offset_x, int offset_y, bool mirror_x, bool mirror_y,
                 bool swap_xy);
    ~GiddyDisplay() override;

    void SetupUI() override;
    void SetPreviewImage(std::unique_ptr<LvglImage> image) override;
    void SetStatus(const char* status) override;
    void SetEmotion(const char* emotion) override;
    void SetChatMessage(const char* role, const char* content) override;
    void ShowNotification(const char* notification, int duration_ms = 3000) override;
    void SetPowerSaveMode(bool on) override;

    void PlaySleepSequence();
    void PlayWakeSequence();
    void PlayFarewellSequence();
    void SetFaceRotation(int degrees);

private:
    lv_obj_t* home_bar_ = nullptr;
    lv_obj_t* dashboard_ = nullptr;
    lv_obj_t* feedback_panel_ = nullptr;
    lv_obj_t* feedback_label_ = nullptr;
    lv_obj_t* preview_toolbar_ = nullptr;
    esp_timer_handle_t moment_timer_ = nullptr;
    esp_timer_handle_t idle_timer_ = nullptr;
    esp_timer_handle_t feedback_timer_ = nullptr;
    std::mutex personality_mutex_;
    std::string moment_fallback_ = "neutral";
    uint32_t moment_generation_ = 0;
    uint32_t idle_sequence_ = 0;
    int64_t moment_deadline_us_ = 0;
    int64_t idle_deadline_us_ = 0;
    int last_visual_state_ = -1;
    bool moment_active_ = false;
    bool controls_after_moment_ = true;
    bool boot_played_ = false;
    bool sleeping_ = false;
    bool farewell_active_ = false;
    int face_rotation_degrees_ = 0;
    uint32_t preview_fit_scale_ = 256;
    uint32_t preview_scale_ = 256;
    int32_t preview_rotation_ = 0;

    void ApplyFaceRotationLocked();
    void AdjustPreviewZoom(int direction);
    void RotatePreview();
    void ExtendPreviewTimeout();
    void ShowDashboard(bool visible);
    void SetControlsVisible(bool visible);
    void HideFeedback();
    void AddActionButton(lv_obj_t* parent, const char* label, const char* action_id,
                         uint32_t background, uint32_t foreground, int x, int y);
    bool HasEmotion(const char* emotion) const;
    bool StartMoment(const char* emotion, int duration_ms, const char* fallback,
                     bool controls_after);
    bool PlayBootSequence();
    void FinishMoment(uint32_t generation);
    void CancelMoment();
    void SetActivityEmotion(const char* emotion);
    const char* ResolveActivityEmotion() const;
    void ArmIdleTimer();
    void HandleIdleTimer();
    static bool IsActivityEmotion(const char* emotion);
    static void OnMomentTimer(void* arg);
    static void OnIdleTimer(void* arg);
    static void OnFeedbackTimer(void* arg);
    static void OnTalkClicked(lv_event_t* event);
    static void OnDashboardClicked(lv_event_t* event);
    static void OnBackClicked(lv_event_t* event);
    static void OnActionClicked(lv_event_t* event);
    static void OnPreviewZoomOut(lv_event_t* event);
    static void OnPreviewRotate(lv_event_t* event);
    static void OnPreviewZoomIn(lv_event_t* event);
};

#endif
