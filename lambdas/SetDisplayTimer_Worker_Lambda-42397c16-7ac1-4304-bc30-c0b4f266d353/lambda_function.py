import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
iot_data = boto3.client('iot-data', region_name='us-east-2')

def lambda_handler(event, context):
    logger.info(f"Evento recibido: {event}")
    plant_name = event.get('plant_name')
    duration_seconds = event.get('duration_seconds')
    if not plant_name or duration_seconds is None:
        logger.error("Payload inválido: falta 'plant_name' o 'duration_seconds'.")
        return
    try:
        # Asegurarse que la duración es un entero positivo
        timeout = int(duration_seconds)
        if timeout <= 0: raise ValueError
    except (ValueError, TypeError):
        logger.error(f"Valor de 'duration_seconds' inválido: {duration_seconds}")
        return
    
    # El estado deseado para el shadow
    desired_state = {"displayOffTimeoutSec": timeout}
    payload = json.dumps({"state": {"desired": desired_state}})
    try:
        iot_data.update_thing_shadow(thingName=plant_name, payload=payload)
        logger.info(f"Shadow actualizado para {plant_name}: {payload}")
    except Exception as e:
        logger.error(f"Error al actualizar shadow para {plant_name}: {e}")