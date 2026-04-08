"""
Lambda Inferencia predicción de demanda para E-commerce en AWS
Autor: Adrián Blasco Lozano
Descripción: Recibe peticiones del API Gateway, llama al endpoint
             de SageMaker y guarda las predicciones en DynamoDB y S3.
Activado por: API Gateway POST /prediccion y GET /predicciones/{store_id}
"""

import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sagemaker_runtime = boto3.client('sagemaker-runtime')
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        http_method = event.get('httpMethod', 'POST')

        # GET /predicciones/{store_id}
        if http_method == 'GET':
            return get_predicciones(event)

        # POST /prediccion
        return post_prediccion(event)

    except Exception as e:
        logger.error(f"Error en LambdaInferencia: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def post_prediccion(event):
    """Llama a SageMaker y guarda la predicción en DynamoDB y S3."""

    body = json.loads(event.get('body', '{}'))
    store_id = str(body.get('store_id'))
    fecha    = body.get('fecha', datetime.now().strftime('%Y-%m-%d'))

    logger.info(f"Predicción solicitada para Store {store_id} fecha {fecha}")

    # Llamada al endpoint de SageMaker
    endpoint_name = os.environ['SAGEMAKER_ENDPOINT']
    payload = json.dumps({'store_id': store_id, 'fecha': fecha})

    response = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='application/json',
        Body=payload
    )

    resultado = json.loads(response['Body'].read().decode())
    prediccion = resultado.get('prediccion', 0)

    logger.info(f"Predicción obtenida: {prediccion} unidades")

    # Guardar en DynamoDB
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    table.put_item(Item={
        'StoreId': store_id,
        'Fecha': fecha,
        'Prediccion': Decimal(str(prediccion)),
        'Timestamp': datetime.now().isoformat()
    })

    # Guardar en S3 output
    output_bucket = os.environ['OUTPUT_BUCKET']
    output_key = f'predicciones/prediccion_{store_id}_{fecha}.json'

    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps({
            'store_id': store_id,
            'fecha': fecha,
            'prediccion': prediccion
        }),
        ContentType='application/json'
    )

    logger.info(f"Predicción guardada en DynamoDB y s3://{output_bucket}/{output_key}")

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'store_id': store_id,
            'fecha': fecha,
            'prediccion_unidades': prediccion
        })
    }


def get_predicciones(event):
    """Consulta predicciones históricas de una tienda desde DynamoDB."""

    store_id = event.get('pathParameters', {}).get('store_id')

    logger.info(f"Consultando predicciones para Store {store_id}")

    table = dynamodb.Table(os.environ['TABLE_NAME'])
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('StoreId').eq(store_id)
    )

    items = response.get('Items', [])

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'store_id': store_id,
            'predicciones': items
        }, default=str)
    }
