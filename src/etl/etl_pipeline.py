"""
ETL Pipeline — Predicción de Demanda para E-commerce en AWS
Autor: Adrián Blasco Lozano — UOC Máster IA
Descripción: Script de limpieza y transformación del dataset Rossmann.
             Se ejecuta desde CloudShell o SageMaker Processing Job.
             Lee desde S3 raw y escribe en S3 processed.
Ejecución: python3 etl_pipeline.py
"""

import boto3
import pandas as pd
import io
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

s3 = boto3.client('s3', region_name='us-east-1')

RAW_BUCKET       = 'prediccion-demanda-raw-319501512128'
PROCESSED_BUCKET = 'prediccion-demanda-processed-319501512128'

def extract():
    """Lee train.csv y store.csv desde S3 raw."""
    logger.info("Leyendo train.csv desde S3...")
    train_obj = s3.get_object(Bucket=RAW_BUCKET, Key='rossmann/train.csv')
    train_df = pd.read_csv(io.BytesIO(train_obj['Body'].read()), low_memory=False)

    logger.info("Leyendo store.csv desde S3...")
    store_obj = s3.get_object(Bucket=RAW_BUCKET, Key='rossmann/store.csv')
    store_df = pd.read_csv(io.BytesIO(store_obj['Body'].read()))

    logger.info(f"Datos cargados: {len(train_df)} filas en train, {len(store_df)} filas en store")
    return train_df, store_df


def transform(train_df, store_df):
    """Limpia y transforma los datos."""

    # Merge por Store
    df = pd.merge(train_df, store_df, on='Store', how='left')

    # Filtrar tiendas cerradas y ventas nulas
    df = df[(df['Open'] == 1) & (df['Sales'] > 0)]
    logger.info(f"Filas tras filtrar cerradas: {len(df)}")

    # Eliminar duplicados
    antes = len(df)
    df = df.drop_duplicates()
    logger.info(f"Duplicados eliminados: {antes - len(df)}")

    # Convertir fecha
    df['Date'] = pd.to_datetime(df['Date'])

    # Variables temporales
    df['Year']      = df['Date'].dt.year
    df['Month']     = df['Date'].dt.month
    df['Week']      = df['Date'].dt.isocalendar().week.astype(int)
    df['DayOfYear'] = df['Date'].dt.dayofyear

    # Tratar nulos
    df['CompetitionDistance'] = df['CompetitionDistance'].fillna(
        df['CompetitionDistance'].median()
    )
    promo_cols = [
        'Promo2SinceWeek', 'Promo2SinceYear',
        'CompetitionOpenSinceMonth', 'CompetitionOpenSinceYear'
    ]
    for col in promo_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    if 'PromoInterval' in df.columns:
        df['PromoInterval'] = df['PromoInterval'].fillna('None')

    # Codificar variables categóricas
    df['StoreType']    = df['StoreType'].astype('category').cat.codes
    df['Assortment']   = df['Assortment'].astype('category').cat.codes
    df['StateHoliday'] = df['StateHoliday'].astype('category').cat.codes

    # Eliminar columnas no necesarias
    df = df.drop(columns=[c for c in ['Open', 'PromoInterval'] if c in df.columns])

    nulos = df.isnull().sum().sum()
    logger.info(f"Nulos restantes: {nulos}")
    logger.info(f"Filas finales: {len(df)}")
    logger.info(f"Columnas: {list(df.columns)}")

    return df


def load(df):
    """Guarda el dataset procesado en S3 processed."""
    fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_key = f'rossmann/train_clean_{fecha}.csv'

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    s3.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=output_key,
        Body=csv_buffer.getvalue(),
        ContentType='text/csv'
    )

    logger.info(f"Datos guardados en s3://{PROCESSED_BUCKET}/{output_key}")
    return output_key


if __name__ == '__main__':
    train_df, store_df = extract()
    df_clean = transform(train_df, store_df)
    output_key = load(df_clean)
    logger.info(f"ETL completado. Archivo: {output_key}")
