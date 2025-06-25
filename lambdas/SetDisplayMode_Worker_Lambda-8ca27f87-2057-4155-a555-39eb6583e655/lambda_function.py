import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
iot_data = boto3.client('iot-data', region_name='us-east-2')

def lambda_handler(event, context):
    logger.info(f"Evento recibido: {event}")
    plant_name = event.get('plant_name')
    mode = event.get('mode')
    if not plant_name or mode not in ["Info", "Face"]:
        logger.error("Payload inválido: falta 'plant_name' o 'mode'.")
        return
    desired_state = {"displayMode": mode}
    payload = json.dumps({"state": {"desired": desired_state}})
    try:
        iot_data.update_thing_shadow(thingName=plant_name, payload=payload)
        logger.info(f"Shadow actualizado para {plant_name}: {payload}")
    except Exception as e:
        logger.error(f"Error al actualizar shadow para {plant_name}: {e}")