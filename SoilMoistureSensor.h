#ifndef SOIL_MOISTURE_SENSOR_H
#define SOIL_MOISTURE_SENSOR_H

#include <Arduino.h>

enum class MoistureStatus { DRY, DAMP, WET };

class SoilMoistureSensor {
private:
    int pin;
    int dryCalibrationValue;
    int wetCalibrationValue;

public:
    SoilMoistureSensor(int sensorPin, int dryCalVal, int wetCalVal);
    int readRaw();
    int getMoisturePercentage(int rawValue);
};

#endif