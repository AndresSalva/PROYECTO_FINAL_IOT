#include "OledController.h"
#include "config.h"

OledController::OledController() 
    : display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET),
      currentStatus(MoistureStatus::WET),
      lastFrameTime(0),
      animationFrame(0),
      frameInterval(90)
{}

bool OledController::begin() {
    #ifdef PIN_OLED_SDA 
        Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
    #endif

    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
        Serial.println(F("Fallo al inicializar la pantalla OLED"));
        return false;
    }
    display.clearDisplay();
    display.display();
    return true;
}

// Dibuja un icono de sol simple usando un círculo y líneas.
void OledController::drawSunIcon(int x, int y) {
    display.fillCircle(x + 8, y + 8, 5, SSD1306_WHITE); // Centro del sol
    // Rayos del sol
    for (int i = 0; i < 360; i += 45) {
        float angle = i * 3.14159 / 180;
        int x1 = x + 8 + 6 * cos(angle);
        int y1 = y + 8 + 6 * sin(angle);
        int x2 = x + 8 + 9 * cos(angle);
        int y2 = y + 8 + 9 * sin(angle);
        display.drawLine(x1, y1, x2, y2, SSD1306_WHITE);
    }
}

// Dibuja un icono de luna simple usando dos círculos superpuestos.
void OledController::drawMoonIcon(int x, int y) {
    display.fillCircle(x + 6, y + 8, 6, SSD1306_WHITE); // Círculo blanco
    display.fillCircle(x + 9, y + 7, 6, SSD1306_BLACK); // Círculo negro para crear la media luna
    // Pequeñas estrellas decorativas
    display.drawPixel(x + 1, y + 2, SSD1306_WHITE);
    display.drawPixel(x + 14, y + 14, SSD1306_WHITE);
}

// Dibuja un icono de gota de agua.
void OledController::drawDropletIcon(int x, int y) {
    // La base redonda de la gota
    display.fillCircle(x + 6, y + 9, 5, SSD1306_WHITE); 
    
    // La punta superior de la gota
    display.fillTriangle(
        x + 1, y + 10,
        x + 11, y + 10,
        x + 6, y + 0,
        SSD1306_WHITE // El color que faltaba y fue corregido.
    );
}

// --- FUNCIÓN showInfo REORGANIZADA PARA MAYOR CLARIDAD ---
void OledController::showInfo(int humidity, const String& light, const String& humidityStatus) {
    // Pausa la animación de la cara para que no se redibuje sobre esta pantalla.
    lastFrameTime = millis() + 100000; 

    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);

    // --- 1. Título ---
    String title = "INFORMACION";
    int16_t x1, y1;
    uint16_t w, h;
    display.getTextBounds(title, 0, 0, &x1, &y1, &w, &h);
    display.setCursor((SCREEN_WIDTH - w) / 2, 4); // Centrado en la zona superior
    display.print(title);
    
    // --- 2. Sección de Humedad ---
    drawDropletIcon(10, 18);          // Icono
    display.setCursor(30, 22);        // Posición del texto del estado
    display.print(humidityStatus);    // "Seco", "Humeda", etc.
    
    // Muestra el porcentaje alineado a la derecha
    String humidityText = String(humidity) + "%";
    display.getTextBounds(humidityText, 0, 0, &x1, &y1, &w, &h);
    display.setCursor(SCREEN_WIDTH - w - 10, 22);
    display.print(humidityText);

    // Dibuja la barra de progreso de humedad
    display.drawRect(10, 34, 108, 8, SSD1306_WHITE);
    int barWidth = map(humidity, 0, 100, 0, 104); // Mapea el % al ancho de la barra
    display.fillRect(12, 36, barWidth, 4, SSD1306_WHITE);

    // --- 3. Sección de Luz ---
    if (light == "Luminoso") {
        drawSunIcon(10, 48);
    } else {
        drawMoonIcon(10, 48);
    }
    display.setCursor(30, 52);
    display.print(light);
    
    // Actualiza la pantalla física para mostrar todo lo dibujado
    display.display();
}

// --- RESTO DE MÉTODOS (sin cambios) ---

void OledController::setFace(MoistureStatus newStatus) {
    if (newStatus == currentStatus) return;
    currentStatus = newStatus;
    animationFrame = 0;
    lastFrameTime = 0; 
}

void OledController::updateAnimation() {
    if (millis() - lastFrameTime > frameInterval) {
        lastFrameTime = millis();
        display.clearDisplay();
        switch (currentStatus) {
            case MoistureStatus::WET:  animateHappyFace();   break;
            case MoistureStatus::DAMP: animateNeutralFace(); break;
            case MoistureStatus::DRY:  animateSadFace();     break;
        }
        display.display();
    }
}

void OledController::animateHappyFace() {
    frameInterval = 80;
    if (animationFrame > 30 && animationFrame < 35) { // Parpadeo
        display.drawFastHLine(44, 30, 15, SSD1306_WHITE);
        display.drawFastHLine(74, 30, 15, SSD1306_WHITE);
    } else {
        display.drawLine(44, 32, 51, 25, SSD1306_WHITE);
        display.drawLine(51, 25, 58, 32, SSD1306_WHITE);
        display.drawLine(74, 32, 81, 25, SSD1306_WHITE);
        display.drawLine(81, 25, 88, 32, SSD1306_WHITE);
    }
    // Sonrisa
    display.drawCircleHelper(65, 45, 10, 4, SSD1306_WHITE);
    display.drawCircleHelper(65, 45, 10, 8, SSD1306_WHITE);
    display.drawPixel(65, 55, SSD1306_WHITE);
    animationFrame = (animationFrame + 1) % 40;
}

void OledController::animateNeutralFace() {
    frameInterval = 90;
    if (animationFrame < 40 || animationFrame > 45) { // Ojos abiertos
        display.fillCircle(54, 30, 4, SSD1306_WHITE);
        display.fillCircle(78, 30, 4, SSD1306_WHITE);
    } else { // Parpadeo
        display.drawFastHLine(50, 30, 8, SSD1306_WHITE);
        display.drawFastHLine(74, 30, 8, SSD1306_WHITE);
    }
    // Boca
    display.drawFastHLine(54, 48, 25, SSD1306_WHITE);
    animationFrame = (animationFrame + 1) % 50;
}

void OledController::animateSadFace() {
    frameInterval = 100;
    // Ojos
    display.drawFastHLine(44, 25, 12, SSD1306_WHITE);
    display.drawFastHLine(74, 25, 12, SSD1306_WHITE);
    // Boca triste
    display.drawCircleHelper(65, 45, 12, 1, SSD1306_WHITE);
    display.drawCircleHelper(65, 45, 12, 2, SSD1306_WHITE);
    display.drawPixel(65, 33, SSD1306_WHITE);

    // Lágrima cayendo
    int tearY = 28 + (animationFrame * 2); 
    if (tearY < 58) { 
        display.fillCircle(80, tearY, 2, SSD1306_WHITE);
    }
    animationFrame = (animationFrame + 1) % 32;
}

void OledController::showMessage(const String& line1, const String& line2) {
    lastFrameTime = millis() + 100000; // Pausa animación
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println(line1);
    if (line2.length() > 0) {
        display.setCursor(0, 30);
        display.println(line2);
    }
    display.display();
}

void OledController::clear() {
    display.clearDisplay();
    display.display();
}