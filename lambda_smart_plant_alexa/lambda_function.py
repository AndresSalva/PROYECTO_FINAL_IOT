# -*- coding: utf-8 -*-

import logging
import ask_sdk_core.utils as ask_utils
import boto3
import json
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

# Configuración de logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Clientes de AWS ---
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('users') 
iot_data = boto3.client('iot-data', region_name='us-east-2')

# --- FUNCIONES DE AYUDA ---

def _get_plant_shadow(handler_input):
    """Obtiene el estado 'reported' del shadow de la planta asociada al usuario."""
    try:
        user_id = handler_input.request_envelope.session.user.user_id
        user_response = users_table.get_item(Key={'userId': user_id})
        if 'Item' not in user_response or not user_response['Item'].get('plants'):
            return None, None, "No tienes plantas asociadas a tu cuenta."
        plant_name = user_response['Item']['plants'][0]
        shadow = iot_data.get_thing_shadow(thingName=plant_name)
        payload = json.loads(shadow['payload'].read().decode('utf-8'))
        return plant_name, payload.get('state', {}).get('reported', {}), None
    except Exception as e:
        logger.error(f"Error en _get_plant_shadow: {e}")
        return None, None, "Hubo un problema al consultar la información de tu planta."

def _update_plant_shadow(plant_name, desired_state):
    """Función para actualizar el estado 'desired' del shadow."""
    try:
        payload = json.dumps({"state": {"desired": desired_state}})
        logger.info(f"Actualizando shadow para '{plant_name}' con payload: {payload}")
        iot_data.update_thing_shadow(thingName=plant_name, payload=payload)
        return True, None
    except Exception as e:
        logger.error(f"Error al actualizar el shadow: {e}")
        return False, "Tuve un problema al enviar el comando a tu planta."

def _parse_duration(duration_str):
    """Convierte una cadena de duración ISO 8601 (PT...M...S) a segundos."""
    if not duration_str or not duration_str.startswith('PT'):
        return 0
    
    seconds = 0
    duration_str = duration_str[2:]
    
    if 'H' in duration_str:
        parts = duration_str.split('H')
        seconds += int(parts[0]) * 3600
        duration_str = parts[1]
    
    if 'M' in duration_str:
        parts = duration_str.split('M')
        seconds += int(parts[0]) * 60
        duration_str = parts[1]
        
    if 'S' in duration_str:
        seconds += int(duration_str.replace('S', ''))
        
    return seconds


# --- HANDLERS DE LA SKILL ---

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler para cuando el usuario lanza la skill sin un intent específico."""
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)
    def handle(self, handler_input):
        speak_output = "¡Hola! Bienvenido a Smart Plant."
        return handler_input.response_builder.speak(speak_output).ask("").response

class SetDisplayModeIntentHandler(AbstractRequestHandler):
    """Handler para cambiar el modo de la pantalla (INFO/FACE)."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("SetDisplayModeIntent")(handler_input)

    def handle(self, handler_input):
        plant_name, _, error_message = _get_plant_shadow(handler_input)
        if error_message:
            return handler_input.response_builder.speak(error_message).ask("").response
        
        try:
            resolutions = handler_input.request_envelope.request.intent.slots["mode"].resolutions
            mode = resolutions.resolutions_per_authority[0].values[0].value.name if resolutions else None
            if mode not in ["Info", "Face"]:
                return handler_input.response_builder.speak("No entendí a qué modo quieres cambiar.").ask("").response
            
            speak_output = f"De acuerdo, cambiando a modo {mode.lower()}."
            success, error_msg = _update_plant_shadow(plant_name, {"displayMode": mode})
            if not success:
                speak_output = error_msg

            return handler_input.response_builder.speak(speak_output).ask("").response
            
        except (AttributeError, IndexError):
            return handler_input.response_builder.speak("No te entendí. Prueba a decir 'cambia a modo información'.").ask("").response
        except Exception as e:
            logger.error(f"Error en SetDisplayModeIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema.").ask("").response


class SetDisplayPowerIntentHandler(AbstractRequestHandler):
    """Handler para encender o apagar la pantalla. VERSIÓN FINAL Y ROBUSTA."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("SetDisplayPowerIntent")(handler_input)

    def handle(self, handler_input):
        plant_name, _, error_message = _get_plant_shadow(handler_input)
        if error_message:
            return handler_input.response_builder.speak(error_message).ask("").response
        try:
            resolutions = handler_input.request_envelope.request.intent.slots["power"].resolutions
            power_command = resolutions.resolutions_per_authority[0].values[0].value.name if resolutions else None
            if power_command not in ["ON", "OFF"]:
                return handler_input.response_builder.speak("No entendí si quieres encender o apagar.").ask("").response

            is_on = (power_command == "ON")
            action_text = "encendiendo" if is_on else "apagando"
            speak_output = f"Entendido, {action_text} la pantalla."
            
            # --- CÓDIGO CORREGIDO Y SIMPLIFICADO ---
            # Se envía únicamente el estado deseado para 'displayOn'.
            # El ESP32 es ahora responsable de gestionar las implicaciones de este comando
            # (como cancelar un temporizador si se recibe un 'apagar').
            desired_state = {"displayOn": is_on}
            
            success, error_msg = _update_plant_shadow(plant_name, desired_state)
            if not success:
                speak_output = error_msg

            return handler_input.response_builder.speak(speak_output).ask("").response
            
        except (AttributeError, IndexError):
            return handler_input.response_builder.speak("No te entendí. Prueba a decir 'enciende la pantalla'.").ask("").response
        except Exception as e:
            logger.error(f"Error en SetDisplayPowerIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema.").ask("").response


class SetDisplayTimerIntentHandler(AbstractRequestHandler):
    """Handler para poner un temporizador para apagar la pantalla. VERSIÓN FINAL Y ROBUSTA."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("SetDisplayTimerIntent")(handler_input)

    def handle(self, handler_input):
        plant_name, _, error_message = _get_plant_shadow(handler_input)
        if error_message:
            return handler_input.response_builder.speak(error_message).ask("").response

        try:
            duration_iso = ask_utils.get_slot_value(handler_input=handler_input, slot_name="duration")
            timeout_seconds = _parse_duration(duration_iso)

            if timeout_seconds <= 0:
                return handler_input.response_builder.speak("No entendí la duración. Por favor, inténtalo de nuevo.").ask("").response
            
            # Se envía únicamente el deseo del temporizador. 
            # El ESP32 se encargará de encender la pantalla si es necesario.
            desired_state = {
                "displayOffTimeoutSec": timeout_seconds
            }
            
            success, error_msg = _update_plant_shadow(plant_name, desired_state)
            
            if not success:
                speak_output = error_msg
            else:
                minutes = timeout_seconds // 60
                seconds = timeout_seconds % 60
                time_str = ""
                if minutes > 0:
                    time_str += f"{minutes} minuto{'s' if minutes > 1 else ''}"
                if seconds > 0:
                    if time_str: time_str += " y "
                    time_str += f"{seconds} segundo{'s' if seconds > 1 else ''}"
                
                speak_output = f"Entendido, apagaré la pantalla en {time_str}."

            return handler_input.response_builder.speak(speak_output).ask("").response

        except Exception as e:
            logger.error(f"Error en SetDisplayTimerIntentHandler: {e}")
            return handler_input.response_builder.speak("Lo siento, tuve un problema al configurar el temporizador.").ask("").response


class PlantStatusIntentHandler(AbstractRequestHandler):
    """Handler para el estado general de la planta."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("PlantStatusIntent")(handler_input)
    def handle(self, handler_input):
        plant_name, reported, error_message = _get_plant_shadow(handler_input)
        if error_message: return handler_input.response_builder.speak(error_message).ask("").response
        percent_humidity = reported.get('percentHumidity', 0)
        status_humidity = reported.get('statusHumidity', 'desconocido').lower()
        light_status = reported.get('lightStatus', 'desconocido').lower()
        mood_message = ""
        if status_humidity == 'seco': mood_message = "Tu planta está triste porque tiene la tierra muy seca. ¡Necesita agua!"
        elif status_humidity == 'casi seco': mood_message = "Tu planta se siente indiferente. La tierra está empezando a secarse."
        elif status_humidity == 'humeda': mood_message = "¡Tu planta está feliz! Tiene suficiente agua y se siente a gusto."
        else: mood_message = "No estoy segura de cómo se siente tu planta."
        light_message = f"Actualmente, el ambiente es {light_status}."
        speak_output = f"{mood_message} {light_message} Como resumen, la humedad es del {percent_humidity} por ciento."
        
        return handler_input.response_builder.speak(speak_output).ask("").response

class GetHumidityIntentHandler(AbstractRequestHandler):
    """Handler para obtener solo la humedad."""
    def can_handle(self, handler_input): return ask_utils.is_intent_name("GetHumidityIntent")(handler_input)
    def handle(self, handler_input):
        _, reported, error_message = _get_plant_shadow(handler_input)
        if error_message: return handler_input.response_builder.speak(error_message).ask("").response
        percent = reported.get('percentHumidity', 'desconocida')
        status = reported.get('statusHumidity', 'desconocido')
        speak_output = f"La humedad es del {percent} por ciento, lo que significa que la tierra está {status}."
        
        return handler_input.response_builder.speak(speak_output).ask("").response

class GetLightStatusIntentHandler(AbstractRequestHandler):
    """Handler para obtener solo el estado de la luz."""
    def can_handle(self, handler_input): return ask_utils.is_intent_name("GetLightStatusIntent")(handler_input)
    def handle(self, handler_input):
        _, reported, error_message = _get_plant_shadow(handler_input)
        if error_message: return handler_input.response_builder.speak(error_message).ask("").response
        status = reported.get('lightStatus', 'desconocido').lower()
        speak_output = f"El nivel de luz actual donde se encuentra la planta es {status}."
        
        return handler_input.response_builder.speak(speak_output).ask("").response

class CloseSkillIntentHandler(AbstractRequestHandler):
    """Handler para cerrar la skill."""
    def can_handle(self, handler_input): return ask_utils.is_intent_name("CloseSkillIntent")(handler_input)
    def handle(self, handler_input): return handler_input.response_builder.speak("¡Hasta luego!").set_should_end_session(True).response

class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Handler para los intents de Cancelar y Parar de Amazon."""
    def can_handle(self, handler_input): return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))
    def handle(self, handler_input): return handler_input.response_builder.speak("¡Adiós!").set_should_end_session(True).response

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

# --- CONSTRUCTOR DE LA SKILL Y REGISTRO DE HANDLERS ---
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