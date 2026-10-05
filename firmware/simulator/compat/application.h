#pragma once
/* Stub de Application para el simulador: solo el estado del dispositivo,
 * que el display consulta para decidir qué mostrar, y los hooks que la UI
 * de Giddy invoca (botones táctiles, acciones rápidas). */
#include <cstdio>
#include <functional>
#include <string>
#include <string_view>
#include "device_state.h"

class Application {
public:
    static Application& GetInstance() {
        static Application instance;
        return instance;
    }
    DeviceState GetDeviceState() const { return state_; }
    bool SetDeviceState(DeviceState s) {
        state_ = s;
        return true;
    }
    void Schedule(std::function<void()>&& cb) {
        if (cb) cb();
    }
    void PlaySound(const std::string_view&) {}
    void ToggleChatState() { printf("[sim] ToggleChatState (botón hablar)\n"); }
    void RunQuickAction(const std::string& action_id) {
        printf("[sim] RunQuickAction(%s)\n", action_id.c_str());
    }

private:
    DeviceState state_ = kDeviceStateIdle;
};
