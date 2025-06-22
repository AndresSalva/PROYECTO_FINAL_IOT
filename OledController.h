#ifndef OLED_CONTROLLER_H
#define OLED_CONTROLLER_H

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "SoilMoistureSensor.h" 

class OledController {
private:
    Adafruit_SSD1306 display;

    MoistureStatus currentStatus;
    unsigned long lastFrameTime;
    int animationFrame;
    int frameInterval;

    void animateHappyFace();
    void animateNeutralFace();
    void animateSadFace();

    void drawSunIcon(int x, int y);
    void drawMoonIcon(int x, int y);
    void drawDropletIcon(int x, int y);

public:
    OledController();
    bool begin();
    void setFace(MoistureStatus newStatus);
    void updateAnimation(); 
    void showMessage(const String& line1, const String& line2 = "");
    void clear();
    void showInfo(int humidity, const String& light, const String& humidityStatus);
};

#endif