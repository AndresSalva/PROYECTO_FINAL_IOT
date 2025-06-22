#include "SoilMoistureSensor.h"

SoilMoistureSensor::SoilMoistureSensor(int sensorPin, int dryCalVal, int wetCalVal) 
    : pin(sensorPin), 
      dryCalibrationValue(dryCalVal),
      wetCalibrationValue(wetCalVal)
{}

int SoilMoistureSensor::readRaw() {
    return analogRead(pin);
}

int SoilMoistureSensor::getMoisturePercentage(int rawValue) {
    long percentage = map(rawValue, dryCalibrationValue, wetCalibrationValue, 0, 100); 
    return constrain(percentage, 0, 100);
}