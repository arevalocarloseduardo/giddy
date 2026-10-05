#pragma once
/* Stub de Application para el simulador: solo el estado del dispositivo,
 * que el display consulta para decidir qué mostrar. */
#include <functional>
#include <string_view>
#include "device_state.h"

class Application {
public:
    static Application& GetInstance() {
        static Application instance;
        return instance;
    }
    DeviceState GetDeviceState() const { return state_; }
    void SetDeviceState(DeviceState s) { state_ = s; }
    void Schedule(std::function<void()> cb) { if (cb) cb(); }
    void PlaySound(std::string_view) {}

private:
    DeviceState state_ = kDeviceStateIdle;
};
