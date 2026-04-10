"""
ETL Pipeline v2 Predicción de Demanda para E-commerce en AWS
Autor: Adrián Blasco Lozano
Descripción: Script de limpieza, transformación y normalización del dataset Rossmann.
             Genera splits train/validation/test y los guarda en S3 processed.
             Se ejecuta desde CloudShell o SageMaker Processing Job.
Ejecución: python3 etl_pipeline.py
Cambios v2:
    - Normalización de variables numéricas (MinMaxScaler)
    - Generación de splits train/validation/test (70/15/15)
    - Guardado de splits en S3 processed
"""

import boto3
import pandas as pd
import numpy as np
import io
import logging
import json
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

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
    """Limpia, transforma y normaliza los datos."""

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

    # Tratar nulos en CompetitionDistance con la mediana
    mediana_comp = df['CompetitionDistance'].median()
    df['CompetitionDistance'] = df['CompetitionDistance'].fillna(mediana_comp)

    # Tratar nulos en columnas de promocion con 0
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

    # Codificar variables categoricas
    df['StoreType']    = df['StoreType'].astype('category').cat.codes
    df['Assortment']   = df['Assortment'].astype('category').cat.codes
    df['StateHoliday'] = df['StateHoliday'].astype('category').cat.codes

    # Eliminar columnas no necesarias
    df = df.drop(columns=[c for c in ['Open', 'PromoInterval'] if c in df.columns])

    # NORMALIZACIÓN
    # La variable objetivo Sales no se normaliza, se predice en escala original
    cols_normalizar = [
        'Customers', 'CompetitionDistance',
        'CompetitionOpenSinceMonth', 'CompetitionOpenSinceYear',
        'Promo2SinceWeek', 'Promo2SinceYear'
    ]
    cols_normalizar = [c for c in cols_normalizar if c in df.columns]

    scaler = MinMaxScaler()
    df[cols_normalizar] = scaler.fit_transform(df[cols_normalizar])

    # Guardar parametros del scaler para poder invertir en inferencia
    scaler_params = {
        'columnas': cols_normalizar,
        'min_': scaler.data_min_.tolist(),
        'max_': scaler.data_max_.tolist(),
        'scale_': scaler.scale_.tolist()
    }

    nulos = df.isnull().sum().sum()
    logger.info(f"Nulos restantes tras limpieza y normalizacion: {nulos}")
    logger.info(f"Filas finales: {len(df)}")
    logger.info(f"Columnas: {list(df.columns)}")
    logger.info(f"Variables normalizadas: {cols_normalizar}")

    return df, scaler_params


def split_data(df):
    """Genera splits train/validation/test ordenados por fecha."""

    # Ordenar por fecha para respetar la temporalidad
    df = df.sort_values('Date').reset_index(drop=True)

    n = len(df)
    train_end  = int(n * 0.70)
    val_end    = int(n * 0.85)

    train_df = df.iloc[:train_end]
    val_df   = df.iloc[train_end:val_end]
    test_df  = df.iloc[val_end:]

    logger.info(f"Split train:      {len(train_df)} filas ({len(train_df)/n*100:.1f}%)")
    logger.info(f"Split validation: {len(val_df)} filas ({len(val_df)/n*100:.1f}%)")
    logger.info(f"Split test:       {len(test_df)} filas ({len(test_df)/n*100:.1f}%)")

    return train_df, val_df, test_df


def upload_csv(df, key, description):
    """Sube un DataFrame como CSV a S3 processed."""
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    s3.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=key,
        Body=buffer.getvalue(),
        ContentType='text/csv'
    )
    logger.info(f"{description} guardado en s3://{PROCESSED_BUCKET}/{key}")


def load(df, scaler_params, train_df, val_df, test_df):
    """Guarda todos los artefactos en S3 processed."""

    fecha = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Dataset completo procesado
    upload_csv(df, f'rossmann/train_clean_{fecha}.csv', 'Dataset completo')

    # Splits
    upload_csv(train_df, f'rossmann/splits/train_{fecha}.csv', 'Split train')
    upload_csv(val_df,   f'rossmann/splits/validation_{fecha}.csv', 'Split validation')
    upload_csv(test_df,  f'rossmann/splits/test_{fecha}.csv', 'Split test')

    # Parametros del scaler en JSON
    s3.put_object(
        Bucket=PROCESSED_BUCKET,
        Key=f'rossmann/splits/scaler_params_{fecha}.json',
        Body=json.dumps(scaler_params, indent=2),
        ContentType='application/json'
    )
    logger.info(f"Parametros del scaler guardados en S3")

    return fecha


if __name__ == '__main__':
    logger.info("=== ETL Pipeline v2 iniciado ===")

    train_df, store_df = extract()
    df_clean, scaler_params = transform(train_df, store_df)
    train_split, val_split, test_split = split_data(df_clean)
    fecha = load(df_clean, scaler_params, train_split, val_split, test_split)

    logger.info("=== ETL Pipeline v2 completado correctamente ===")
    logger.info(f"Archivos guardados con timestamp: {fecha}")
