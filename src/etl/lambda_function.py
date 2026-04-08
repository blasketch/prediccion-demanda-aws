"""
Lambda ETL trigger
Autor: Adrián Blasco Lozano
Descripción: Detecta la subida de un CSV a S3 raw y registra el evento.
             El procesamiento real se ejecuta mediante SageMaker Processing.
Activado por: evento S3 ObjectCreated en el bucket raw
"""
import json
import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    try:
        # Obtener información del archivo subido desde el evento S3
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']

        logger.info(f"Nuevo archivo detectado: s3://{bucket}/{key}")
        logger.info("Evento registrado. SageMaker Processing Job se lanzará en A4.")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'mensaje': 'Evento S3 procesado correctamente',
                'bucket': bucket,
                'archivo': key
            })
        }

    except KeyError:
        # Invocación manual sin evento S3
        logger.info("Invocación manual detectada — sin evento S3")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'mensaje': 'Lambda ETL activa y funcionando',
                'modo': 'invocación manual'
            })
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
