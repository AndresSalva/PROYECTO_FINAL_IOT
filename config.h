#ifndef CONFIG_H
#define CONFIG_H

// --- HARDWARE PIN DEFINITIONS ---
#define PIN_SOIL_MOISTURE 35
#define PIN_LIGHT_SENSOR  34
#define PIN_SERVO         19
#define PIN_OLED_SDA      23
#define PIN_OLED_SCL      22

// --- LOGIC THRESHOLDS & PARAMETERS ---
#define SOIL_DRY_PERCENT_THRESHOLD   25
#define SOIL_WET_PERCENT_THRESHOLD   75
#define SOIL_HYSTERESIS_PERCENT      5 
#define SOIL_CALIBRATION_DRY 3800
#define SOIL_CALIBRATION_WET 2600

// Higher ADC value means it's darker.
#define LIGHT_THRESHOLD      2000
#define LIGHT_HYSTERESIS     300 

// --- ACTUATOR PARAMETERS ---
#define SERVO_ANGLE_BRIGHT   90
#define SERVO_ANGLE_DARK     0

// --- OLED DISPLAY CONFIGURATION ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1 

// --- NETWORK & CLOUD CONFIGURATION ---
const unsigned long PUBLISH_INTERVAL = 5UL * 60UL * 1000UL; // 5 minutes

#define AWS_IOT_ENDPOINT   "a2ji0g9lxroj8h-ats.iot.us-east-2.amazonaws.com"
#define AWS_IOT_PORT       8883
#define AWS_IOT_CLIENT_ID  "smart_plant_001"
#define AWS_SHADOW_TOPIC_UPDATE "$aws/things/smart_plant_001/shadow/update"
#define AWS_SHADOW_TOPIC_GET "$aws/things/smart_plant_001/shadow/get"
#define AWS_SHADOW_TOPIC_GET_ACCEPTED "$aws/things/smart_plant_001/shadow/get/accepted"
#define AWS_SHADOW_TOPIC_DELTA "$aws/things/smart_plant_001/shadow/update/delta"
#endif