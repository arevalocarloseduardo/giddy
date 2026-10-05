#pragma once
/* Stub de Assets: en la placa carga la partición de assets (GIFs, fuentes).
 * En el simulador el avatar se carga desde un directorio en main.cc. */
class Assets {
public:
    static Assets& GetInstance() {
        static Assets instance;
        return instance;
    }
    bool partition_valid() const { return false; }
    bool Apply(bool /*refresh_display_theme*/ = true) { return true; }
};
