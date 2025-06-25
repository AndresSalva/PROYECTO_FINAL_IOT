import json
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('smart_plant_events_history')

def lambda_handler(event, context):
    print("Evento recibido:", json.dumps(event))

    try:
        state = event.get('current', {}).get('state', {})
        if 'reported' not in state:
            print("No se encontró 'state.reported' en el evento. Saliendo.")
            return {'statusCode': 200, 'body': 'No-op'}
            
        reported = state['reported']
        thing_name = event.get('thingName', 'smart_plant_001')
        
        timestamp = int(datetime.utcnow().timestamp())
        
        item = {
            'thingName': thing_name,
            'timestamp': timestamp,
            'percentHumidity': int(reported.get('percentHumidity', 0)),
            'statusHumidity': reported.get('statusHumidity', 'desconocido'),
            'displayMode': reported.get('displayMode', 'desconocido'),
            'displayOn': reported.get('displayOn', 'desconocido'),
            #'displayOffTimeoutSec': int(reported.get('displayOffTimeoutSec', 0)),          
            #'shadeServoAngle': int(reported.get('shadeServoAngle', -1)),
            'lightStatus': reported.get('lightStatus', 'desconocido'),
        }

        item.pop('servoAngle', None)

        table.put_item(Item=item)
        print(f"Guardado histórico exitoso: {item}")
        return {'statusCode': 200, 'body': json.dumps('Éxito histórico')}

    except Exception as e:
        print(f"Error detectado: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}