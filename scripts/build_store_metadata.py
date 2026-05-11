"""
Construye store_metadata.csv a partir de uno de los splits de entrenamiento
y lo sube a S3. Este CSV contiene la metadata estática de cada tienda
(StoreType, Assortment, CompetitionDistance, etc.) que el Lambda Inferencia
necesitará para completar las features que el usuario no proporciona en la API.
"""
import boto3
import pandas as pd
from io import BytesIO

BUCKET = "prediccion-demanda-processed-319501512128"
SPLIT_KEY = "rossmann/splits/train_20260410_054619.csv"
OUTPUT_KEY = "output/store_metadata.csv"

META_COLS = [
    "StoreType", "Assortment", "CompetitionDistance",
    "CompetitionOpenSinceMonth", "CompetitionOpenSinceYear",
    "Promo2", "Promo2SinceWeek", "Promo2SinceYear",
]

s3 = boto3.client("s3")

print(f"Descargando s3://{BUCKET}/{SPLIT_KEY} ...")
obj = s3.get_object(Bucket=BUCKET, Key=SPLIT_KEY)
df = pd.read_csv(BytesIO(obj["Body"].read()))
print(f"  Filas: {len(df):,} | Columnas: {len(df.columns)}")

# Verificamos que las columnas existen
missing = [c for c in META_COLS if c not in df.columns]
if missing:
    raise ValueError(f"Columnas faltantes en el split: {missing}")

# Tomamos la primera ocurrencia por tienda (la metadata es estática)
store_metadata = df.groupby("Store")[META_COLS].first().reset_index()
print(f"  Tiendas únicas: {len(store_metadata)}")

# Guardamos local y subimos a S3
local_path = "/tmp/store_metadata.csv"
store_metadata.to_csv(local_path, index=False)
print(f"  CSV local: {local_path}")

s3.upload_file(local_path, BUCKET, OUTPUT_KEY)
print(f"\nSubido a s3://{BUCKET}/{OUTPUT_KEY}")
print(f"\nPreview de las primeras filas:")
print(store_metadata.head().to_string(index=False))
