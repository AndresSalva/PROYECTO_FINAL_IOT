#include "SmartPlant.h"
#include "secrets.h"

// Crear la instancia de la planta inteligente, pasándole solo los certificados.
// El WiFi se configurará a través de un portal web.
SmartPlant planta(AWS_PRIVATE_KEY, AWS_CERTIFICATE, AWS_ROOT_CA);

void setup() {
    planta.setup();
}

void loop() {
    planta.loop();
}