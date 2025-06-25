# -*- coding: utf-8 -*-

import logging
import json
import boto3
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import os

# --- CONFIGURACIÓN ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
REGION_NAME = os.environ.get('AWS_REGION', 'us-east-2')

# --- CLIENTES DE AWS ---
lambda_client = boto3.client('lambda', region_name=REGION_NAME)
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
iot_data = boto3.client('iot-data', region_name=REGION_NAME)

# --- Nombres de recursos ---
USERS_TABLE_NAME = 'users'
POWER_WORKER_NAME = 'SetDisplayPower_Worker_Lambda'
MODE_WORKER_NAME = 'SetDisplayMode_Worker_Lambda'
TIMER_WORKER_NAME = 'SetDisplayTimer_Worker_Lambda'

users_table = dynamodb.Table(USERS_TABLE_NAME)

# --- FUNCIONES DE AYUDA ---
def get_plant_name_from_user(handler_input):
    try:
        user_id = handler_input.request_envelope.session.user.user_id
        response = users_table.get_item(Key={'userId': user_id})
        if 'Item' in response and response['Item'].get('plants'):
            return response['Item']['plants'][0], None
        return None, "No tienes plantas asociadas a tu cuenta."
    except Exception as e:
        logger.error(f"Error buscando planta: {e}")
        return None, "Tuve un problema al buscar tu planta."

def get_plant_shadow(handler_input):
    plant_name, error = get_plant_name_from_user(handler_input)
    if error: return None, None, error
    try:
        shadow = iot_data.get_thing_shadow(thingName=plant_name)
        payload = json.loads(shadow['payload'].read().decode('utf-8'))
        return plant_name, payload.get('state', {}).get('reported', {}), None
    except Exception as e:
        logger.error(f"Error en get_plant_shadow para {plant_name}: {e}")
        return None, None, "Hubo un problema al consultar la información de tu planta."

def parse_duration(duration_str):
    if not duration_str or not duration_str.startswith('PT'): return 0
    seconds, duration_str = 0, duration_str[2:]
    if 'H' in duration_str:
        parts = duration_str.split('H'); seconds += int(parts[0]) * 3600; duration_str = parts[1]
    if 'M' in duration_str:
        parts = duration_str.split('M'); seconds += int(parts[0]) * 60; duration_str = parts[1]
    if 'S' in duration_str:
        seconds += int(duration_str.replace('S', ''))
    return seconds

# --- HANDLERS ---

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_request_type("LaunchRequest")(handler_input)
    def handle(self, handler_input):
        speak_output = "¡Hola! Bienvenido a Smart Plant."
        return handler_input.response_builder.speak(speak_output).ask("").response

class SetDisplayPowerIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("SetDisplayPowerIntent")(handler_input)
    def handle(self, handler_input):
        plant_name, error = get_plant_name_from_user(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        try:
            resolutions = handler_input.request_envelope.request.intent.slots["power"].resolutions
            power_command = resolutions.resolutions_per_authority[0].values[0].value.name if resolutions else None
            if power_command not in ["ON", "OFF"]:
                return handler_input.response_builder.speak("No entendí si quieres encender o apagar.").ask("").response
            
            worker_payload = json.dumps({"plant_name": plant_name, "power": power_command})
            lambda_client.invoke(FunctionName=POWER_WORKER_NAME, InvocationType='Event', Payload=worker_payload)
            
            action_text = "encendiendo" if power_command == "ON" else "apagando"
            speak_output = f"Entendido, {action_text} la pantalla."
            return handler_input.response_builder.speak(speak_output).ask("").response
        except Exception as e:
            logger.error(f"Error en SetDisplayPowerIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema.").ask("").response

class SetDisplayModeIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("SetDisplayModeIntent")(handler_input)
    def handle(self, handler_input):
        plant_name, error = get_plant_name_from_user(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        try:
            resolutions = handler_input.request_envelope.request.intent.slots["mode"].resolutions
            mode_interno = resolutions.resolutions_per_authority[0].values[0].value.name if resolutions else None
            if mode_interno not in ["Info", "Face"]:
                return handler_input.response_builder.speak("No entendí a qué modo quieres cambiar.").ask("").response
            
            worker_payload = json.dumps({"plant_name": plant_name, "mode": mode_interno})
            lambda_client.invoke(FunctionName=MODE_WORKER_NAME, InvocationType='Event', Payload=worker_payload)
            
            nombres_para_hablar = {"Info": "información", "Face": "cara"}
            nombre_bonito = nombres_para_hablar.get(mode_interno)
            
            speak_output = f"De acuerdo, cambiando a modo {nombre_bonito}."
            return handler_input.response_builder.speak(speak_output).ask("").response
        except Exception as e:
            logger.error(f"Error en SetDisplayModeIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema.").ask("").response

class SetDisplayTimerIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("SetDisplayTimerIntent")(handler_input)
    def handle(self, handler_input):
        plant_name, error = get_plant_name_from_user(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        try:
            duration_iso = ask_utils.get_slot_value(handler_input, "duration")
            timeout_seconds = parse_duration(duration_iso)
            if timeout_seconds <= 0: return handler_input.response_builder.speak("No entendí la duración. Por favor, inténtalo de nuevo.").ask("").response
            
            worker_payload = json.dumps({"plant_name": plant_name, "duration_seconds": timeout_seconds})
            lambda_client.invoke(FunctionName=TIMER_WORKER_NAME, InvocationType='Event', Payload=worker_payload)

            minutes = timeout_seconds // 60
            seconds = timeout_seconds % 60
            time_str = ""
            if minutes > 0: time_str += f"{minutes} minuto{'s' if minutes > 1 else ''}"
            if seconds > 0:
                if time_str: time_str += " y "
                time_str += f"{seconds} segundo{'s' if seconds > 1 else ''}"
            
            speak_output = f"Entendido, apagaré la pantalla en {time_str}."
            return handler_input.response_builder.speak(speak_output).ask("").response
        except Exception as e:
            logger.error(f"Error en SetDisplayTimerIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema al configurar el temporizador.").ask("").response

class PlantStatusIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("PlantStatusIntent")(handler_input)
    def handle(self, handler_input):
        _, reported, error = get_plant_shadow(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        percent = reported.get('percentHumidity', 0)
        status = reported.get('statusHumidity', 'desconocido').lower()
        light = reported.get('lightStatus', 'desconocido').lower()
        mood = {"seco": "Tu planta está triste porque tiene la tierra muy seca. ¡Necesita agua!",
                "casi seco": "Tu planta se siente indiferente. La tierra está empezando a secarse.",
                "humeda": "¡Tu planta está feliz! Tiene suficiente agua y se siente a gusto."}.get(status, "No estoy segura de cómo se siente tu planta.")
        light_msg = f"Actualmente, el ambiente es {light}."
        speak_output = f"{mood} {light_msg} Como resumen, la humedad es del {percent} por ciento."
        return handler_input.response_builder.speak(speak_output).ask("").response

class GetHumidityIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("GetHumidityIntent")(handler_input)
    def handle(self, handler_input):
        _, reported, error = get_plant_shadow(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        percent = reported.get('percentHumidity', 'desconocida')
        status = reported.get('statusHumidity', 'desconocido')
        speak_output = f"La humedad es del {percent} por ciento, lo que significa que la tierra está {status}."
        return handler_input.response_builder.speak(speak_output).ask("").response

class GetLightStatusIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("GetLightStatusIntent")(handler_input)
    def handle(self, handler_input):
        _, reported, error = get_plant_shadow(handler_input)
        if error: return handler_input.response_builder.speak(error).ask("").response
        status = reported.get('lightStatus', 'desconocido').lower()
        speak_output = f"El nivel de luz actual donde se encuentra la planta es {status}."
        return handler_input.response_builder.speak(speak_output).ask("").response

class CloseSkillIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("CloseSkillIntent")(handler_input)
    def handle(self, handler_input):
        return handler_input.response_builder.speak("¡Hasta luego!").set_should_end_session(True).response

class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))
    def handle(self, handler_input):
        return handler_input.response_builder.speak("¡Adiós!").set_should_end_session(True).response

class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)
    def handle(self, handler_input):
        speak_output = "Puedes pedirme el estado, cambiar el modo de la pantalla a 'información' o 'cara', o encender y apagar la pantalla."
        return handler_input.response_builder.speak(speak_output).ask("").response

class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)
    def handle(self, handler_input):
        speak_output = "Lo siento, no entendí eso. Puedes preguntarme cómo está tu planta."
        return handler_input.response_builder.speak(speak_output).ask("").response

class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input): return ask_utils.is_request_type("SessionEndedRequest")(handler_input)
    def handle(self, handler_input): return handler_input.response_builder.response

class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception): return True
    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        speak_output = "Lo siento, tuve un problema para hacer lo que me pediste."
        return handler_input.response_builder.speak(speak_output).ask("").response

# --- CONSTRUCTOR Y REGISTRO ---
sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(PlantStatusIntentHandler())
sb.add_request_handler(GetHumidityIntentHandler())
sb.add_request_handler(GetLightStatusIntentHandler())
sb.add_request_handler(SetDisplayModeIntentHandler())
sb.add_request_handler(SetDisplayPowerIntentHandler())
sb.add_request_handler(SetDisplayTimerIntentHandler())
sb.add_request_handler(CloseSkillIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()