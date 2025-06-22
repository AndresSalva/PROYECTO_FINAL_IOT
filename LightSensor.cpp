#include "LightSensor.h"

LightSensor::LightSensor(int sensorPin, int lightThreshold, int lightHysteresis) 
    : pin(sensorPin), 
      threshold(lightThreshold), 
      hysteresis(lightHysteresis), 
      lastStatus(LightStatus::BRIGHT)
{}

int LightSensor::readRaw() {
    return analogRead(pin);
}

LightStatus LightSensor::getStatus(int rawValue) {
    if (rawValue > (threshold + hysteresis)) {
        lastStatus = LightStatus::DARK;
    } else if (rawValue < (threshold - hysteresis)) {
        lastStatus = LightStatus::BRIGHT;
    }
    return lastStatus;
}