#pragma once
/* Stub mínimo del codec: el display solo mira el volumen para el ícono de mute. */
class AudioCodec {
public:
    int output_volume() const { return output_volume_; }
    void SetOutputVolume(int v) { output_volume_ = v; }

private:
    int output_volume_ = 70;
};
