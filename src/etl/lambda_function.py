"""
Lambda ETL predicción de demanda para E-commerce en AWS
Autor: Adrián Blasco Lozano
Descripción: Limpia y transforma el dataset Rossmann desde S3 raw
             y carga el resultado en S3 processed.
Activado por: evento S3 ObjectCreated en el bucket raw
"""

import json
import boto3
import pandas as pd
import io
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        raw_bucket = os.environ['RAW_BUCKET']
        processed_bucket = os.environ['PROCESSED_BUCKET']

        logger.info("Iniciando proceso ETL")

        # 1 EXTRACCIÓN
        logger.info("Leyendo train.csv desde S3...")
        train_obj = s3.get_object(Bucket=raw_bucket, Key='rossmann/train.csv')
        train_df = pd.read_csv(io.BytesIO(train_obj['Body'].read()), low_memory=False)

        logger.info("Leyendo store.csv desde S3...")
        store_obj = s3.get_object(Bucket=raw_bucket, Key='rossmann/store.csv')
        store_df = pd.read_csv(io.BytesIO(store_obj['Body'].read()))

        logger.info(f"Datos cargados: {len(train_df)} filas en train, {len(store_df)} filas en store")

        # 2 TRANSFORMACIÓN
        # Merge de los dos datasets por Store
        df = pd.merge(train_df, store_df, on='Store', how='left')

        # Filtrar tiendas cerradas y ventas nulas
        df = df[(df['Open'] == 1) & (df['Sales'] > 0)]
        logger.info(f"Filas tras filtrar cerradas: {len(df)}")

        # Eliminar duplicados
        antes = len(df)
        df = df.drop_duplicates()
        logger.info(f"Duplicados eliminados: {antes - len(df)}")

        # Convertir fecha a datetime
        df['Date'] = pd.to_datetime(df['Date'])

        # Extraer variables temporales
        df['Year']      = df['Date'].dt.year
        df['Month']     = df['Date'].dt.month
        df['Week']      = df['Date'].dt.isocalendar().week.astype(int)
        df['DayOfYear'] = df['Date'].dt.dayofyear

        # Tratar nulos en CompetitionDistance con la mediana
        mediana = df['CompetitionDistance'].median()
        df['CompetitionDistance'] = df['CompetitionDistance'].fillna(mediana)

        # Tratar nulos en columnas de promoción con 0
        promo_cols = [
            'Promo2SinceWeek', 'Promo2SinceYear',
            'CompetitionOpenSinceMonth', 'CompetitionOpenSinceYear'
        ]
        for col in promo_cols:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # Tratar nulos en PromoInterval
        if 'PromoInterval' in df.columns:
            df['PromoInterval'] = df['PromoInterval'].fillna('None')

        # Codificar variables categóricas
        df['StoreType']    = df['StoreType'].astype('category').cat.codes
        df['Assortment']   = df['Assortment'].astype('category').cat.codes
        df['StateHoliday'] = df['StateHoliday'].astype('category').cat.codes

        # Eliminar columnas no necesarias para el modelo
        df = df.drop(columns=[c for c in ['Open', 'PromoInterval'] if c in df.columns])

        # Verificar nulos restantes
        nulos = df.isnull().sum().sum()
        logger.info(f"Nulos restantes tras limpieza: {nulos}")
        logger.info(f"Filas finales procesadas: {len(df)}")
        logger.info(f"Columnas: {list(df.columns)}")

        # 3 CARGA
        fecha_proceso = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_key = f'rossmann/train_clean_{fecha_proceso}.csv'

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)

        s3.put_object(
            Bucket=processed_bucket,
            Key=output_key,
            Body=csv_buffer.getvalue(),
            ContentType='text/csv'
        )

        logger.info(f"Datos guardados en s3://{processed_bucket}/{output_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'mensaje': 'ETL completado correctamente',
                'filas_entrada': len(train_df),
                'filas_salida': len(df),
                'nulos_restantes': int(nulos),
                'archivo_output': output_key
            })
        }

    except Exception as e:
        logger.error(f"Error en ETL: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
