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
| Procesamiento | AWS Lambda (trigger) + SageMaker Processing Job |
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
├── infrastructure/
│   └── template.yaml                    # Infraestructura como código (SAM/CloudFormation)
│
├── src/
│   ├── etl/
│   │   ├── lambda_function.py           # Lambda ETL — trigger S3 (detecta nuevos archivos)
│   │   └── etl_pipeline.py              # Script ETL completo (ejecutable desde CloudShell o SageMaker)
│   └── inferencia/
│       └── lambda_function.py           # Lambda Inferencia — predicciones via API Gateway
│
├── notebooks/
│   └── exploracion.ipynb                # Análisis exploratorio del dataset
│
├── streamlit/
│   └── dashboard.py                     # Dashboard de visualización (Streamlit)
│
├── data/
│   └── sample/
│       └── train_sample.csv             # Muestra representativa del dataset (500 filas)
│
└── README.md                            # Documentación del proyecto
```

---

## Dataset

- **Fuente:** [Rossmann Store Sales — Kaggle](https://www.kaggle.com/datasets/pratyushakar/rossmann-store-sales)
- **Formato:** CSV
- **Volumen:** ~1.017.209 filas (train.csv) + información de tiendas (store.csv)
- **Descripción:** Histórico de ventas diarias de 1.115 tiendas en 7 países europeos
- **Columnas principales:** `Store`, `Date`, `Sales`, `Customers`, `Open`, `Promo`, `StateHoliday`, `SchoolHoliday`

---

## Estructura S3 (Data Lake)

```
s3://prediccion-demanda-raw-319501512128/
    └── rossmann/
        ├── train.csv          # Histórico de ventas (~1M filas, 38MB)
        └── store.csv          # Información de tiendas (1.115 filas)

s3://prediccion-demanda-processed-319501512128/
    └── rossmann/
        └── train_clean_YYYYMMDD_HHMMSS.csv   # Dataset limpio tras ETL (66MB)

s3://prediccion-demanda-output-319501512128/
    └── predicciones/
        └── predicciones_YYYYMMDD.csv          # Predicciones generadas por el modelo
```

---

## Pipeline ETL

El proceso ETL se ejecuta mediante el script `src/etl/etl_pipeline.py`, invocado desde CloudShell o SageMaker Processing Job. La función Lambda (`src/etl/lambda_function.py`) actúa como **trigger**, detectando automáticamente nuevos archivos subidos al bucket raw y orquestando el proceso.

**Flujo completo:**

1. **Trigger:** Se sube un CSV al bucket S3 raw → Lambda detecta el evento `ObjectCreated`
2. **Extracción:** Lectura de `train.csv` y `store.csv` desde S3 `/raw/rossmann/`
3. **Limpieza:**
   - Filtrado de tiendas cerradas (`Open=0`) y ventas nulas (`Sales=0`)
   - Eliminación de duplicados
   - Tratamiento de nulos en `CompetitionDistance` (mediana) y columnas de promoción (0)
4. **Transformación:**
   - Merge de `train.csv` con `store.csv` por `Store`
   - Extracción de variables temporales: `Year`, `Month`, `Week`, `DayOfYear`
   - Codificación de variables categóricas: `StoreType`, `Assortment`, `StateHoliday`
5. **Carga:** Escritura del dataset procesado en S3 `/processed/rossmann/`

**Resultado del ETL ejecutado:**
- Filas entrada: 1.017.209
- Filas salida: 844.338
- Nulos restantes: 0
- Columnas finales: 20

---

## Infraestructura como Código

La infraestructura completa está definida en `infrastructure/template.yaml` usando **AWS SAM**. Para desplegarla:

```bash
# Descargar el template desde GitHub
wget https://raw.githubusercontent.com/blasketch/prediccion-demanda-aws/main/infrastructure/template.yaml

# Crear carpetas de código necesarias
mkdir -p src/etl src/inferencia

# Descargar código de las Lambdas
wget -O src/etl/lambda_function.py https://raw.githubusercontent.com/blasketch/prediccion-demanda-aws/main/src/etl/lambda_function.py
wget -O src/inferencia/lambda_function.py https://raw.githubusercontent.com/blasketch/prediccion-demanda-aws/main/src/inferencia/lambda_function.py

# Desplegar con SAM
sam deploy \
  --template-file template.yaml \
  --stack-name prediccion-demanda \
  --s3-bucket sam-deploy-<account-id> \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --region us-east-1 \
  --no-confirm-changeset
```

---

## Recursos AWS desplegados

| Recurso | Nombre | ARN |
|---|---|---|
| S3 Raw | prediccion-demanda-raw-319501512128 | `arn:aws:s3:::prediccion-demanda-raw-319501512128` |
| S3 Processed | prediccion-demanda-processed-319501512128 | `arn:aws:s3:::prediccion-demanda-processed-319501512128` |
| S3 Output | prediccion-demanda-output-319501512128 | `arn:aws:s3:::prediccion-demanda-output-319501512128` |
| DynamoDB | PrediccionesTable | `arn:aws:dynamodb:us-east-1:319501512128:table/PrediccionesTable` |
| Lambda ETL | prediccion-demanda-LambdaETL | `arn:aws:lambda:us-east-1:319501512128:function:prediccion-demanda-LambdaETL` |
| Lambda Inferencia | prediccion-demanda-LambdaInferencia | `arn:aws:lambda:us-east-1:319501512128:function:prediccion-demanda-LambdaInferencia` |

---

## Tecnologías utilizadas

- **Python 3.12** — lenguaje principal
- **Pandas** — procesamiento y limpieza de datos
- **Boto3** — SDK de AWS para Python
- **Scikit-learn** — preprocesamiento y modelado
- **XGBoost** — modelo de predicción
- **Streamlit** — dashboard de visualización
- **AWS SAM** — despliegue de infraestructura como código
- **AWS:** S3, Lambda, SageMaker, DynamoDB, API Gateway, EventBridge, CloudWatch, IAM, KMS

---

## Seguridad

- Buckets S3 privados — acceso público bloqueado
- Cifrado en reposo: SSE-KMS (`alias/aws/s3`)
- Cifrado en tránsito: HTTPS obligatorio (BucketPolicy con `aws:SecureTransport`)
- IAM: rol `LabRole` de AWS Academy (mínimo privilegio en entorno académico)
- EventBridge: `State: DISABLED` en entorno de pruebas para conservar créditos

---

## Contexto Académico

| Campo | Detalle |
|---|---|
| **Asignatura** | Proyecto de Inteligencia Artificial y Big Data |
| **Institución** | Universitat Oberta de Catalunya (UOC) |
| **Máster** | Máster en Inteligencia Artificial |
| **Actividad actual** | A3 — Preparación y carga de datos en AWS |

---

## Autor

**Adrián Blasco Lozano**
Máster en Inteligencia Artificial — UOC
