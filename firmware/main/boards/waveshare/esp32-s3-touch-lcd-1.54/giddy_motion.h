#ifndef GIDDY_MOTION_H
#define GIDDY_MOTION_H

#include <driver/i2c_master.h>
#include <functional>
#include <qmi8658.h>

class GiddyMotion {
public:
    using OrientationCallback = std::function<void(int degrees)>;
    using ShakeCallback = std::function<void()>;

    GiddyMotion(i2c_master_bus_handle_t bus, OrientationCallback orientation_callback,
                ShakeCallback shake_callback);

    bool Start();

private:
    static void MotionTask(void* arg);
    void Run();
    int ClassifyOrientation(float x, float y, float z) const;

    i2c_master_bus_handle_t bus_;
    qmi8658_dev_t imu_{};
    OrientationCallback orientation_callback_;
    ShakeCallback shake_callback_;
};

#endif
