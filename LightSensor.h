#ifndef LIGHT_SENSOR_H
#define LIGHT_SENSOR_H

#include <Arduino.h>

enum class LightStatus {
    BRIGHT,
    DARK
};

class LightSensor {
private:
    int pin;
    int threshold;
    int hysteresis;
    LightStatus lastStatus;

public:
    LightSensor(int sensorPin, int lightThreshold, int lightHysteresis);
    int readRaw();
    LightStatus getStatus(int rawValue);
};

#endif