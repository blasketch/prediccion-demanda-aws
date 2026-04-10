"""
ETL Pipeline v3 Predicción de Demanda para E-commerce en AWS
Autor: Adrián Blasco Lozano
Descripción: Script de limpieza, transformación y normalización del dataset Rossmann.
             Genera splits train/validation/test y los guarda en S3 processed.
             Se ejecuta desde CloudShell o SageMaker Processing Job.
Cambios v3:
    - Manejo de errores en lecturas S3
    - Variables de entorno para configuración
    - Validación de datos de entrada
    - Logging mejorado con tiempos de ejecución
"""

import boto3
import pandas as pd
import numpy as np
import io
import logging
import json
import os
import time
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Configuración desde variables de entorno o valores por defecto
RAW_BUCKET       = os.environ.get('RAW_BUCKET', 'prediccion-demanda-raw-319501512128')
PROCESSED_BUCKET = os.environ.get('PROCESSED_BUCKET', 'prediccion-demanda-processed-319501512128')
REGION           = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
RAW_PREFIX       = os.environ.get('RAW_PREFIX', 'rossmann')

try:
    s3 = boto3.client('s3', region_name=REGION)
    logger.info(f"Cliente S3 inicializado — region: {REGION}")
except Exception as e:
    logger.error(f"Error inicializando cliente S3: {str(e)}")
    raise


def read_csv_from_s3(bucket, key):
    """Lee un CSV desde S3 con manejo de errores."""
    try:
        logger.info(f"Leyendo s3://{bucket}/{key}...")
        response = s3.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(io.BytesIO(response['Body'].read()), low_memory=False)
        logger.info(f"Leido correctamente: {len(df)} filas, {len(df.columns)} columnas")
        return df
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise FileNotFoundError(f"Archivo no encontrado en S3: s3://{bucket}/{key}")
        elif error_code == 'NoSuchBucket':
            raise FileNotFoundError(f"Bucket no encontrado: {bucket}")
        else:
            raise RuntimeError(f"Error AWS al leer s3://{bucket}/{key}: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error inesperado leyendo s3://{bucket}/{key}: {str(e)}")


def validate_dataframe(df, name, required_cols):
    """Valida que un DataFrame tiene las columnas requeridas."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes en {name}: {missing}")
    if df.empty:
        raise ValueError(f"El DataFrame {name} está vacío")
    logger.info(f"Validacion correcta de {name}: {len(df)} filas, columnas requeridas presentes")


def extract():
    """Lee train.csv y store.csv desde S3 raw con validación."""
    train_df = read_csv_from_s3(RAW_BUCKET, f'{RAW_PREFIX}/train.csv')
    store_df = read_csv_from_s3(RAW_BUCKET, f'{RAW_PREFIX}/store.csv')

    # Validar columnas requeridas
    validate_dataframe(train_df, 'train.csv', [
        'Store', 'Date', 'Sales', 'Open', 'Promo', 'StateHoliday', 'SchoolHoliday'
    ])
    validate_dataframe(store_df, 'store.csv', [
        'Store', 'StoreType', 'Assortment', 'CompetitionDistance'
    ])

    return train_df, store_df


def transform(train_df, store_df):
    """Limpia, transforma y normaliza los datos."""
    try:
        # Merge por Store
        df = pd.merge(train_df, store_df, on='Store', how='left')
        logger.info(f"Merge completado: {len(df)} filas")

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
        mediana_comp = df['CompetitionDistance'].median()
        df['CompetitionDistance'] = df['CompetitionDistance'].fillna(mediana_comp)
        logger.info(f"CompetitionDistance: nulos rellenados con mediana {mediana_comp:.2f}")

        promo_cols = [
            'Promo2SinceWeek', 'Promo2SinceYear',
            'CompetitionOpenSinceMonth', 'CompetitionOpenSinceYear'
        ]
        for col in promo_cols:
            if col in df.columns:
                nulos_col = df[col].isnull().sum()
                df[col] = df[col].fillna(0)
                if nulos_col > 0:
                    logger.info(f"{col}: {nulos_col} nulos rellenados con 0")

        if 'PromoInterval' in df.columns:
            df['PromoInterval'] = df['PromoInterval'].fillna('None')

        # Codificar variables categoricas
        for col in ['StoreType', 'Assortment', 'StateHoliday']:
            if col in df.columns:
                df[col] = df[col].astype('category').cat.codes

        # Eliminar columnas no necesarias
        df = df.drop(columns=[c for c in ['Open', 'PromoInterval'] if c in df.columns])

        # Normalización MinMaxScaler
        cols_normalizar = [
            'Customers', 'CompetitionDistance',
            'CompetitionOpenSinceMonth', 'CompetitionOpenSinceYear',
            'Promo2SinceWeek', 'Promo2SinceYear'
        ]
        cols_normalizar = [c for c in cols_normalizar if c in df.columns]

        scaler = MinMaxScaler()
        df[cols_normalizar] = scaler.fit_transform(df[cols_normalizar])
        logger.info(f"Normalizacion aplicada a: {cols_normalizar}")

        scaler_params = {
            'columnas': cols_normalizar,
            'min_': scaler.data_min_.tolist(),
            'max_': scaler.data_max_.tolist(),
            'scale_': scaler.scale_.tolist()
        }

        # Verificacion final
        nulos = df.isnull().sum().sum()
        if nulos > 0:
            logger.warning(f"ATENCION: quedan {nulos} nulos tras la limpieza")
        else:
            logger.info("Verificacion final: 0 nulos restantes")

        logger.info(f"Filas finales: {len(df)}")
        logger.info(f"Columnas: {list(df.columns)}")

        return df, scaler_params

    except Exception as e:
        logger.error(f"Error en la fase de transformacion: {str(e)}")
        raise


def split_data(df):
    """Genera splits train/validation/test respetando temporalidad."""
    try:
        df = df.sort_values('Date').reset_index(drop=True)
        n = len(df)
        train_end = int(n * 0.70)
        val_end   = int(n * 0.85)

        train_df = df.iloc[:train_end]
        val_df   = df.iloc[train_end:val_end]
        test_df  = df.iloc[val_end:]

        logger.info(f"Split train:      {len(train_df)} filas ({len(train_df)/n*100:.1f}%)")
        logger.info(f"Split validation: {len(val_df)} filas ({len(val_df)/n*100:.1f}%)")
        logger.info(f"Split test:       {len(test_df)} filas ({len(test_df)/n*100:.1f}%)")

        return train_df, val_df, test_df

    except Exception as e:
        logger.error(f"Error en la fase de split: {str(e)}")
        raise


def upload_to_s3(content, key, content_type='text/csv', description=''):
    """Sube contenido a S3 con manejo de errores."""
    try:
        s3.put_object(
            Bucket=PROCESSED_BUCKET,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        logger.info(f"{description} guardado en s3://{PROCESSED_BUCKET}/{key}")
    except ClientError as e:
        raise RuntimeError(f"Error subiendo {key} a S3: {str(e)}")


def load(df, scaler_params, train_df, val_df, test_df):
    """Guarda todos los artefactos en S3 con manejo de errores."""
    try:
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Dataset completo
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        upload_to_s3(buffer.getvalue(), f'{RAW_PREFIX}/train_clean_{fecha}.csv',
                    'text/csv', 'Dataset completo')

        # Splits
        for split_df, nombre in [
            (train_df, 'train'),
            (val_df, 'validation'),
            (test_df, 'test')
        ]:
            buf = io.StringIO()
            split_df.to_csv(buf, index=False)
            upload_to_s3(buf.getvalue(),
                        f'{RAW_PREFIX}/splits/{nombre}_{fecha}.csv',
                        'text/csv', f'Split {nombre}')

        # Scaler params
        upload_to_s3(
            json.dumps(scaler_params, indent=2),
            f'{RAW_PREFIX}/splits/scaler_params_{fecha}.json',
            'application/json', 'Parametros scaler'
        )

        return fecha

    except Exception as e:
        logger.error(f"Error en la fase de carga: {str(e)}")
        raise


if __name__ == '__main__':
    inicio = time.time()
    logger.info("=== ETL Pipeline v3 iniciado ===")
    logger.info(f"RAW_BUCKET: {RAW_BUCKET}")
    logger.info(f"PROCESSED_BUCKET: {PROCESSED_BUCKET}")

    try:
        train_df, store_df = extract()
        df_clean, scaler_params = transform(train_df, store_df)
        train_split, val_split, test_split = split_data(df_clean)
        fecha = load(df_clean, scaler_params, train_split, val_split, test_split)

        duracion = time.time() - inicio
        logger.info(f"=== ETL Pipeline v3 completado en {duracion:.1f} segundos ===")
        logger.info(f"Timestamp: {fecha}")

    except FileNotFoundError as e:
        logger.error(f"Archivo no encontrado: {str(e)}")
        raise
    except ValueError as e:
        logger.error(f"Error de validacion: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise
