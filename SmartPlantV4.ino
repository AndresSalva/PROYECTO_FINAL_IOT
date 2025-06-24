#include "SmartPlant.h"
#include "secrets.h"

SmartPlant planta(AWS_PRIVATE_KEY, AWS_CERTIFICATE, AWS_ROOT_CA);

void setup() {
    planta.setup();
}

void loop() {
    planta.loop();
}