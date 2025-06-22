#include "SmartPlant.h"
#include "config.h" 
#include <ArduinoJson.h>
#include <WiFi.h>
#include <DNSServer.h>
#include <time.h>

// --- CONSTRUCTOR ---
SmartPlant::SmartPlant(const char* privateKey, const char* certificate, const char* rootCA)
    : awsPrivateKey(privateKey), awsCertificate(certificate), awsRootCA(rootCA),
      mqttClient(netClient),
      soilSensor(PIN_SOIL_MOISTURE, SOIL_CALIBRATION_DRY, SOIL_CALIBRATION_WET),
      lightSensor(PIN_LIGHT_SENSOR, LIGHT_THRESHOLD, LIGHT_HYSTERESIS),
      oled(),
      lastMoistureStatus(MoistureStatus::WET),
      lastLightStatus(LightStatus::DARK),
      currentDisplayMode("Face"), 
      isDisplayOn(true),        
      forceDisplayUpdate(false),
      lastPublishTime(0),
      lastDisplayActivityTime(0),
      displayTimeoutDuration(0)
{}

void SmartPlant::setup() {
    Serial.begin(115200);
    
    if (!oled.begin()) {
        Serial.println("Fallo al iniciar OLED. Deteniendo.");
        for (;;);
    }
    oled.showMessage("Iniciando SmartPlant...");
    delay(1500);

    connectWiFi();
    oled.showMessage("WiFi Conectado!", WiFi.localIP().toString());
    delay(2000);
    
    oled.showMessage("Sincronizando NTP...");
    configTime(0, 0, "pool.ntp.org");
    
    time_t now = time(nullptr);
    while (now < 8 * 3600 * 2) { // Espera a que la hora sea válida
        delay(500);
        Serial.print(".");
        now = time(nullptr);
    }
    Serial.println("\n¡Hora sincronizada!");
    oled.showMessage("NTP Sincronizado!");
    delay(1500);
    
    ESP32PWM::allocateTimer(0);
    shadeServo.setPeriodHertz(50);
    shadeServo.attach(PIN_SERVO, 500, 2500);
    shadeServo.write(SERVO_ANGLE_DARK);
    
    setupMQTT();

    oled.showMessage("Sistema Iniciado", "Listo para operar."); 
    delay(1500);

    // Publica el estado inicial del dispositivo al arrancar
    reportState(nullptr); 
    lastPublishTime = millis();
}

void SmartPlant::loop() {
    if (!mqttClient.connected()) {
        oled.showMessage("Conectando a AWS...");
        connectAWS();
    }
    mqttClient.loop();

    // --- Lógica del temporizador de la pantalla ---
    // Si la pantalla está encendida, hay un temporizador activo y ya ha pasado el tiempo, apágala.
    if (isDisplayOn && displayTimeoutDuration > 0 && (millis() - lastDisplayActivityTime >= displayTimeoutDuration)) {
        isDisplayOn = false;
        displayTimeoutDuration = 0; // Resetea el temporizador para que no se vuelva a ejecutar
        forceDisplayUpdate = true;  // Forza un reporte para notificar a la nube que la pantalla se apagó
    }

    // --- Lectura de sensores ---
    int rawLightValue = lightSensor.readRaw();
    int rawMoistureValue = soilSensor.readRaw();
    LightStatus currentLightStatus = lightSensor.getStatus(rawLightValue);
    int humidityPercent = soilSensor.getMoisturePercentage(rawMoistureValue);
    MoistureStatus currentMoistureStatus = determineMoistureStatus(humidityPercent);

    // --- Control del display ---
    if (isDisplayOn) {
        if (currentDisplayMode == "Info") {
            oled.showInfo(humidityPercent, lightStatusToString(currentLightStatus), moistureStatusToString(currentMoistureStatus));
        } else { // Modo "FACE" por defecto
            oled.setFace(currentMoistureStatus);
            oled.updateAnimation();
        }
    } else {
        oled.clear();
    }
    
    // --- Lógica de publicación de estado ---
    bool stateChanged = (currentMoistureStatus != lastMoistureStatus) || (currentLightStatus != lastLightStatus);
    bool timeToPublish = (millis() - lastPublishTime > PUBLISH_INTERVAL);

    // Publica si:
    // 1. Se forzó una actualización (ej: la pantalla se apagó por temporizador).
    // 2. El estado de algún sensor cambió significativamente.
    // 3. Ha pasado el intervalo de tiempo para una publicación periódica.
    if (forceDisplayUpdate || stateChanged || timeToPublish) {
        reportState(nullptr);
        
        // Solo controla los actuadores si el estado de los sensores cambió
        if (stateChanged) {
            controlActuators(currentLightStatus, currentMoistureStatus);
        }
        
        lastMoistureStatus = currentMoistureStatus; 
        lastLightStatus = currentLightStatus;
        forceDisplayUpdate = false; // Resetea el flag de forzado
        lastPublishTime = millis();
    }
    
    delay(20);
}

void SmartPlant::mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.print("Mensaje recibido en el tópico: ");
    Serial.println(topic);

    DynamicJsonDocument doc(512);
    deserializeJson(doc, payload, length);
    
    // Solo procesamos mensajes en el tópico 'delta', que indican cambios en el estado 'desired'
    if (strcmp(topic, AWS_SHADOW_TOPIC_DELTA) == 0) {
        JsonObject state = doc["state"];
        
        // Objeto JSON para acumular las claves del 'desired' que vamos a limpiar (poniéndolas a null)
        DynamicJsonDocument keysToClear(256);
        JsonObject desiredToClear = keysToClear.to<JsonObject>();

        if (state.containsKey("displayMode")) {
            currentDisplayMode = state["displayMode"].as<String>();
            desiredToClear["displayMode"] = nullptr;
        }
        if (state.containsKey("displayOn")) {
            isDisplayOn = state["displayOn"].as<bool>();
            // Si el comando es apagar, también cancela cualquier temporizador pendiente.
            if (!isDisplayOn) {
                displayTimeoutDuration = 0;
            }
            desiredToClear["displayOn"] = nullptr;
        }
        if (state.containsKey("displayOffTimeoutSec")) {
            long timeoutSec = state["displayOffTimeoutSec"].as<long>();
            if (timeoutSec > 0) {
                isDisplayOn = true; // Un temporizador siempre enciende la pantalla primero
                displayTimeoutDuration = timeoutSec * 1000UL;
                lastDisplayActivityTime = millis();
            } else { // Si se envía 0 o un valor negativo, se cancela el temporizador
                displayTimeoutDuration = 0;
            }
            desiredToClear["displayOffTimeoutSec"] = nullptr;
        }

        // Si se procesó al menos un comando del delta, reportar el nuevo estado inmediatamente
        // para confirmar los cambios y limpiar el estado 'desired' en el shadow.
        if (desiredToClear.size() > 0) {
            reportState(&desiredToClear);
        }
    }
}

void SmartPlant::reportState(const JsonObject* keysToClear) {
    DynamicJsonDocument doc(512);
    JsonObject state = doc.createNestedObject("state");
    
    // --- Sección 'reported': Siempre informa el estado actual completo ---
    JsonObject reported = state.createNestedObject("reported");
    
    int humidityPercent = soilSensor.getMoisturePercentage(soilSensor.readRaw());
    MoistureStatus moistureStatus = determineMoistureStatus(humidityPercent);
    LightStatus lightStatus = lightSensor.getStatus(lightSensor.readRaw());
    
    reported["percentHumidity"] = humidityPercent;
    reported["statusHumidity"] = moistureStatusToString(moistureStatus);
    reported["shadeServoAngle"] = getServoTargetAngle(lightStatus); 
    reported["lightStatus"] = lightStatusToString(lightStatus);

    // Estados "controlables" por el usuario
    reported["displayMode"] = currentDisplayMode;
    reported["displayOn"] = isDisplayOn;
    // NOTA: No reportamos 'displayOffTimeoutSec' porque es un comando, no un estado persistente.

    // --- Sección 'desired': Si se nos pide, la limpiamos ---
    // Esto añade ` "desired": { "clave": null, ... } ` al payload.
    if (keysToClear != nullptr && keysToClear->size() > 0) {
        state["desired"] = *keysToClear;
    }
    
    String payload;
    serializeJson(doc, payload);

    Serial.print("Reportando estado: ");
    Serial.println(payload);
    mqttClient.publish(AWS_SHADOW_TOPIC_UPDATE, payload.c_str());
}


// --- Métodos de Ayuda y Control ---

MoistureStatus SmartPlant::determineMoistureStatus(int percent) const {
    // Esta lógica de histéresis es correcta para evitar cambios rápidos
    switch (lastMoistureStatus) {
        case MoistureStatus::WET:
            if (percent < (SOIL_WET_PERCENT_THRESHOLD - SOIL_HYSTERESIS_PERCENT)) return MoistureStatus::DAMP;
            break;
        case MoistureStatus::DAMP:
            if (percent > (SOIL_WET_PERCENT_THRESHOLD + SOIL_HYSTERESIS_PERCENT)) return MoistureStatus::WET;
            else if (percent < (SOIL_DRY_PERCENT_THRESHOLD - SOIL_HYSTERESIS_PERCENT)) return MoistureStatus::DRY;
            break;
        case MoistureStatus::DRY:
            if (percent > (SOIL_DRY_PERCENT_THRESHOLD + SOIL_HYSTERESIS_PERCENT)) return MoistureStatus::DAMP;
            break;
    }
    return lastMoistureStatus;
}

void SmartPlant::controlActuators(LightStatus lightStatus, MoistureStatus moistureStatus) {
    shadeServo.write(getServoTargetAngle(lightStatus));
    oled.setFace(moistureStatus);
}

void SmartPlant::connectWiFi() {
    WiFiManager wm;
    wm.setConfigPortalTimeout(180);
    if (!wm.autoConnect("SmartPlant-Config")) {
        oled.showMessage("Error de WiFi", "Reiniciando...");
        delay(3000);
        ESP.restart(); 
    }
}

void SmartPlant::setupMQTT() {
    netClient.setCACert(awsRootCA);
    netClient.setCertificate(awsCertificate);
    netClient.setPrivateKey(awsPrivateKey);
    
    mqttClient.setServer(AWS_IOT_ENDPOINT, AWS_IOT_PORT);
    // Usar una lambda para pasar el puntero 'this' al callback
    mqttClient.setCallback([this](char* topic, byte* payload, unsigned int length) {
        this->mqttCallback(topic, payload, length);
    });
}

void SmartPlant::connectAWS() {
    int retries = 0;
    while (!mqttClient.connected() && retries < 5) {
        if (mqttClient.connect(AWS_IOT_CLIENT_ID)) {
            oled.showMessage("Conectado a AWS!");
            delay(1500);
            mqttClient.subscribe(AWS_SHADOW_TOPIC_GET_ACCEPTED);
            mqttClient.subscribe(AWS_SHADOW_TOPIC_DELTA); // Suscripción al tópico de deltas
            mqttClient.publish(AWS_SHADOW_TOPIC_GET, ""); // Pide el estado actual al conectar
        } else {
            Serial.print("Fallo de conexión MQTT, rc=");
            Serial.print(mqttClient.state());
            Serial.println(" Reintentando...");
            oled.showMessage("Error AWS", "Reintentando...");
            delay(2000);
            retries++;
        }
    }
}

int SmartPlant::getServoTargetAngle(LightStatus status) const {
    return (status == LightStatus::BRIGHT) ? SERVO_ANGLE_BRIGHT : SERVO_ANGLE_DARK;
}

String SmartPlant::moistureStatusToString(MoistureStatus status) const {
    switch (status) {
        case MoistureStatus::DRY:  return "Seco";
        case MoistureStatus::DAMP: return "Casi seco";
        case MoistureStatus::WET:  return "Humeda";
        default: return "Desconocido";
    }
}

String SmartPlant::lightStatusToString(LightStatus status) const {
    switch (status) {
        case LightStatus::BRIGHT: return "Luminoso";
        case LightStatus::DARK:   return "Oscuro";
        default: return "Desconocido";
    }
}