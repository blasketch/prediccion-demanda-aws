# Predicción de Demanda para E-commerce en AWS

Pipeline completo de predicción de demanda semanal por SKU para empresas de comercio electrónico, desplegado sobre servicios gestionados de AWS.

---

## Descripción del Proyecto

Las empresas de e-commerce pierden millones de euros anualmente por sobrestock y desabastecimiento. Este proyecto automatiza la **predicción semanal de unidades vendidas por producto**, proporcionando a los equipos de compras y logística una estimación cuantitativa y reproducible basada en el histórico de ventas.

**Objetivos:**
- Reducir el exceso de inventario entre un 20% y un 30%
- Elevar la tasa de disponibilidad de producto por encima del 95%
- Automatizar el proceso de predicción sin intervención manual

---

## Arquitectura AWS

El sistema está organizado en ocho zonas funcionales desplegadas sobre AWS:

| Zona | Servicios |
|---|---|
| Ingesta de datos | Amazon S3 (Raw Data) |
| Procesamiento | AWS Lambda + SageMaker Processing Job |
| ML / Entrenamiento | SageMaker Training Job + Amazon S3 (Model Artifacts) |
| Inferencia | SageMaker Endpoint + AWS Lambda + Amazon API Gateway |
| Persistencia | Amazon DynamoDB + Amazon S3 (Predictions) |
| Visualización | Streamlit |
| Observabilidad | Amazon CloudWatch + AWS CloudTrail |
| Seguridad | AWS IAM + AWS KMS |

---

## Estructura del Repositorio

```
prediccion-demanda-aws/
│
├── data/
│   └── sample/                  # Muestra representativa del dataset (500 filas)
│
├── etl/
│   ├── etl_pipeline.py          # Script principal de limpieza y transformación
│   └── upload_s3.py             # Script de carga de datos a S3
│
├── notebooks/
│   └── exploracion.ipynb        # Análisis exploratorio del dataset
│
├── lambda/
│   └── trigger_etl.py           # Función Lambda que orquesta el pipeline ETL
│
├── streamlit/
│   └── dashboard.py             # Dashboard de visualización de predicciones
│
└── README.md
```

---

## Dataset

- **Fuente:** [Rossmann Store Sales — Kaggle](https://www.kaggle.com/competitions/rossmann-store-sales)
- **Formato:** CSV
- **Volumen:** ~1.000.000 filas (train.csv) + información de tiendas (store.csv)
- **Descripción:** Histórico de ventas diarias de 1.115 tiendas en 7 países europeos
- **Columnas principales:** `Store`, `Date`, `Sales`, `Customers`, `Open`, `Promo`, `StateHoliday`, `SchoolHoliday`

---

## Estructura S3 (Data Lake)

```
s3://prediccion-demanda-raw/
    └── rossmann/
        └── train.csv
        └── store.csv

s3://prediccion-demanda-processed/
    └── rossmann/
        └── train_clean.csv

s3://prediccion-demanda-output/
    └── predicciones/
        └── predicciones_semana_XX.csv
```

---

## Pipeline ETL

El proceso ETL se ejecuta mediante un **SageMaker Processing Job** orquestado por AWS Lambda:

1. **Extracción:** Lectura del CSV desde S3 `/raw/`
2. **Limpieza:**
   - Eliminación de valores nulos
   - Eliminación de duplicados
   - Filtrado de registros con ventas = 0 (tiendas cerradas)
3. **Transformación:**
   - Generación de *lag features* (ventas semanas anteriores)
   - Codificación de variables temporales (semana del año, mes, festivos)
   - Normalización de variables numéricas
4. **Carga:** Escritura del dataset procesado en S3 `/processed/`

---

## Tecnologías utilizadas

- **Python 3.10** — lenguaje principal
- **Pandas / NumPy** — procesamiento de datos
- **Boto3** — SDK de AWS para Python
- **Scikit-learn** — preprocesamiento y modelado
- **XGBoost** — modelo de predicción
- **Streamlit** — dashboard de visualización
- **AWS:** S3, Lambda, SageMaker, DynamoDB, API Gateway, CloudWatch, IAM, KMS

---

## Seguridad

- Buckets S3 privados — acceso público bloqueado
- Cifrado en reposo: SSE-KMS
- Cifrado en tránsito: HTTPS
- IAM: principio de mínimo privilegio (rol `LabRole` en AWS Academy)

---

## Contexto Académico

| Campo | Detalle |
|---|---|
| **Asignatura** | Proyecto de Inteligencia Artificial y Big Data |
| **Institución** | Universitat Oberta de Catalunya (UOC) |
| **Máster** | Máster en Inteligencia Artificial |
| **Actividad** | A3 — Preparación y carga de datos en AWS |

---

## Autor

**Adrián Blasco Lozano**
Máster en Inteligencia Artificial — UOC
