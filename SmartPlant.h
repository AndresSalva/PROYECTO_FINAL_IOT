#ifndef SMART_PLANT_H
#define SMART_PLANT_H

#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <WiFiManager.h>
#include "SoilMoistureSensor.h"
#include "LightSensor.h"
#include "OledController.h" 
#include <ArduinoJson.h>

class SmartPlant {
private:
    const char* awsPrivateKey;
    const char* awsCertificate;
    const char* awsRootCA;

    WiFiClientSecure netClient;
    PubSubClient mqttClient;

    SoilMoistureSensor soilSensor;
    LightSensor lightSensor;
    Servo shadeServo;
    OledController oled;

    // --- Variables de estado del dispositivo ---
    MoistureStatus lastMoistureStatus; 
    LightStatus lastLightStatus;       
    String currentDisplayMode;
    bool isDisplayOn;
    bool forceDisplayUpdate; // Flag para forzar una publicación del estado

    // --- Variables para temporizadores y control de tiempo ---
    unsigned long lastPublishTime;    
    unsigned long lastDisplayActivityTime;
    unsigned long displayTimeoutDuration; // en milisegundos
    
    // --- Métodos privados de configuración y conexión ---
    void connectWiFi();
    void setupMQTT();
    void connectAWS();
    void mqttCallback(char* topic, byte* payload, unsigned int length);
    
    // --- Métodos privados de lógica y control ---
    void controlActuators(LightStatus lightStatus, MoistureStatus moistureStatus); 
    
    // Reporta el estado actual a AWS. Si `keysToClear` no es nulo,
    // también limpia las claves correspondientes del estado 'desired' en el shadow.
    void reportState(const JsonObject* keysToClear);

    // --- Métodos `const` (no modifican el estado del objeto) ---
    MoistureStatus determineMoistureStatus(int percent) const;
    int getServoTargetAngle(LightStatus status) const; 
    String moistureStatusToString(MoistureStatus status) const;
    String lightStatusToString(LightStatus status) const;

public:
    SmartPlant(const char* privateKey, const char* certificate, const char* rootCA);
    void setup();
    void loop();
};

#endif