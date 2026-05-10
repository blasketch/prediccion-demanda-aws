"""
Lambda Inferencia - Predicción de demanda Rossmann (R5)

Carga el modelo XGBoost de R4 desde S3, completa las features de tienda
desde store_metadata.csv, predice y guarda en DynamoDB y S3.

Activado por: API Gateway POST /prediccion y GET /predicciones/{store_id}
"""
import json
import os
import logging
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import boto3
import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─────────────────────────────────────────
# Config (env vars + S3 keys)
# ─────────────────────────────────────────
PROCESSED_BUCKET = os.environ["PROCESSED_BUCKET"]
TABLE_NAME       = os.environ["TABLE_NAME"]
OUTPUT_BUCKET    = os.environ["OUTPUT_BUCKET"]

MODEL_KEY      = "output/model.joblib"
STORE_META_KEY = "output/store_metadata.csv"

# AWS clients
s3       = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table    = dynamodb.Table(TABLE_NAME)

# Cold-start cache
_artifact      = None
_store_meta    = None

def load_artifacts():
    """Descarga modelo y metadata desde S3 una sola vez por contenedor."""
    global _artifact, _store_meta
    if _artifact is None:
        logger.info("Cold start: descargando model.joblib desde S3")
        s3.download_file(PROCESSED_BUCKET, MODEL_KEY, "/tmp/model.joblib")
        _artifact = joblib.load("/tmp/model.joblib")
        logger.info(
            f"Modelo cargado | Features: {len(_artifact['features'])} | "
            f"RMSPE test: {_artifact['test_metrics']['RMSPE']:.4f}"
        )
    if _store_meta is None:
        logger.info("Cold start: descargando store_metadata.csv desde S3")
        obj = s3.get_object(Bucket=PROCESSED_BUCKET, Key=STORE_META_KEY)
        _store_meta = pd.read_csv(BytesIO(obj["Body"].read()))
        logger.info(f"Metadata de {len(_store_meta)} tiendas cargada")
    return _artifact, _store_meta

# Handler principal
def lambda_handler(event, context):
    try:
        load_artifacts()
        http_method = event.get("httpMethod", "POST")
        if http_method == "GET":
            return get_predicciones(event)
        return post_prediccion(event)
    except KeyError as e:
        logger.error(f"Falta campo obligatorio: {e}")
        return _response(400, {"error": f"Falta campo obligatorio: {e}"})
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        return _response(500, {"error": str(e)})

# POST /prediccion
def post_prediccion(event):
    """Predice ventas para (tienda, fecha) dados."""
    body = json.loads(event.get("body") or "{}")

    # Validación de inputs
    store_id       = int(body["store_id"])
    fecha_str      = body["fecha"]
    fecha          = pd.to_datetime(fecha_str)
    promo          = int(body.get("promo", 0))
    state_holiday  = int(body.get("state_holiday", 0))
    school_holiday = int(body.get("school_holiday", 0))

    artifact, store_meta = load_artifacts()
    model           = artifact["model"]
    features        = artifact["features"]
    store_stats     = artifact["store_stats"]
    store_dow_stats = artifact["store_dow_stats"]

    if store_id not in store_meta["Store"].values:
        return _response(400, {"error": f"Store {store_id} no existe"})

    # Features de fecha (Rossmann: DOW 1=Lun, 7=Dom)
    day_of_week = fecha.dayofweek + 1

    row = {
        "Store":              store_id,
        "DayOfWeek":          day_of_week,
        "Promo":              promo,
        "StateHoliday":       state_holiday,
        "SchoolHoliday":      school_holiday,
        "Year":               fecha.year,
        "Month":              fecha.month,
        "Week":               int(fecha.isocalendar().week),
        "DayOfYear":          fecha.dayofyear,
        "DayOfMonth":         fecha.day,
        "IsBeginningOfMonth": int(fecha.day <= 10),
        "IsEndOfMonth":       int(fecha.day >= 20),
        "IsWeekend":          int(day_of_week in [6, 7]),
    }

    # Metadata estática de la tienda (8 cols)
    meta = store_meta.loc[store_meta["Store"] == store_id].iloc[0]
    for col in store_meta.columns:
        if col != "Store":
            row[col] = meta[col]

    # Stats por tienda (7 cols)
    stats = store_stats.loc[store_stats["Store"] == store_id].iloc[0]
    for col in store_stats.columns:
        if col != "Store":
            row[col] = stats[col]

    # Stats por (tienda, DOW) (2 cols) con fallback al store-level
    dow_match = store_dow_stats[
        (store_dow_stats["Store"] == store_id) &
        (store_dow_stats["DayOfWeek"] == day_of_week)
    ]
    if len(dow_match) == 0:
        logger.warning(
            f"Sin stats para Store {store_id} DOW {day_of_week}, usando media de tienda"
        )
        row["StoreDOW_Sales_mean"]   = stats["Store_Sales_mean"]
        row["StoreDOW_Sales_median"] = stats["Store_Sales_median"]
    else:
        dow = dow_match.iloc[0]
        for col in store_dow_stats.columns:
            if col not in ("Store", "DayOfWeek"):
                row[col] = dow[col]

    # Reordenar al orden exacto esperado por el modelo
    df = pd.DataFrame([row])
    X = df[features].values

    # Predicción (clip a 0 para evitar valores negativos)
    prediction = float(np.clip(model.predict(X)[0], 0, None))
    logger.info(
        f"Store {store_id} | {fecha_str} | DOW {day_of_week} | "
        f"Promo {promo} → {prediction:.2f}€"
    )

    # Persistir en DynamoDB
    table.put_item(Item={
        "StoreId":    str(store_id),
        "Fecha":      fecha_str,
        "Prediccion": Decimal(str(round(prediction, 2))),
        "Timestamp":  datetime.utcnow().isoformat(),
    })

    # Persistir en S3
    output_key = f"predicciones/prediccion_{store_id}_{fecha_str}.json"
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=json.dumps({
            "store_id":   store_id,
            "fecha":      fecha_str,
            "prediccion": prediction,
        }),
        ContentType="application/json",
    )

    return _response(200, {
        "store_id":            store_id,
        "fecha":               fecha_str,
        "prediccion_unidades": round(prediction, 2),
        "modelo":              "xgboost-r4-final",
        "rmspe_test":          round(artifact["test_metrics"]["RMSPE"], 4),
    })


# GET /predicciones/{store_id}
def get_predicciones(event):
    """Devuelve el histórico de predicciones de una tienda."""
    store_id = event.get("pathParameters", {}).get("store_id")
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("StoreId").eq(str(store_id))
    )
    return _response(200, {
        "store_id":     store_id,
        "predicciones": response.get("Items", []),
    }, default=str)


# Helper de respuesta JSON
def _response(status, body, default=None):
    return {
        "statusCode": status,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body, default=default),
    }
