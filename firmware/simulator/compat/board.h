#pragma once
/* Stub de Board para el simulador: batería, red y codec con valores fijos
 * que se pueden cambiar desde el script o el teclado. */
#include "audio_codec.h"

class Display;

class Board {
public:
    static Board& GetInstance() {
        static Board instance;
        return instance;
    }
    AudioCodec* GetAudioCodec() { return &codec_; }
    Display* GetDisplay() { return display_; }
    void SetDisplay(Display* d) { display_ = d; }
    const char* GetNetworkStateIcon() { return network_icon_; }
    bool GetBatteryLevel(int& level, bool& charging, bool& discharging) {
        level = battery_level_;
        charging = charging_;
        discharging = !charging_;
        return true;
    }
    void SetBattery(int level, bool charging) {
        battery_level_ = level;
        charging_ = charging;
    }
    void SetNetworkIcon(const char* icon) { network_icon_ = icon; }

private:
    AudioCodec codec_;
    Display* display_ = nullptr;
    int battery_level_ = 80;
    bool charging_ = false;
    const char* network_icon_ = "";
};
