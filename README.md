# Predicción de demanda para E-commerce en AWS

Pipeline completo de predicción de demanda diaria por tienda para empresas de comercio electrónico, desplegado sobre servicios gestionados de AWS. Incluye infraestructura como código, ETL automatizado, modelo XGBoost entrenado con feature engineering avanzado, y **despliegue serverless del modelo como API REST autenticada con dashboard Streamlit como cliente visual**.

> **Resultado del modelo final:** RMSPE de **14.83%** en test, una mejora del **61%** respecto al baseline ingenuo.  
> **Sistema desplegado:** API REST con autenticación por API Key, latencia warm de **47 ms**, 0 errores en todas las pruebas funcionales.

---

## Descripción del Proyecto

Las empresas de e-commerce pierden millones de euros anualmente por sobrestock y desabastecimiento. Este proyecto automatiza la **predicción de ventas diarias por tienda**, proporcionando a los equipos de compras y logística una estimación cuantitativa y reproducible basada en el histórico de ventas, accesible mediante una API REST segura y un dashboard interactivo.

**Objetivos:**

- Reducir el exceso de inventario entre un 20% y un 30%
- Elevar la tasa de disponibilidad de producto por encima del 95%
- Automatizar el proceso de predicción sin intervención manual
- Exponer el modelo de forma segura para integración con sistemas externos

## Arquitectura AWS

El sistema está organizado en ocho zonas funcionales desplegadas sobre AWS:

| Zona               | Servicios                                                            |
| ------------------ | -------------------------------------------------------------------- |
| Ingesta de datos   | Amazon S3 (Raw Data)                                                 |
| Procesamiento      | AWS Lambda (trigger) + SageMaker Processing Job                      |
| ML / Entrenamiento | SageMaker Notebook Instance + Amazon S3 (Model Artifacts)            |
| Inferencia         | API Gateway REST + AWS Lambda (Container Image) + Amazon ECR         |
| Persistencia       | Amazon DynamoDB + Amazon S3 (Predictions)                            |
| Visualización      | Streamlit (cliente local de la API)                                  |
| Observabilidad     | Amazon CloudWatch (Logs + Metrics) + AWS X-Ray                       |
| Seguridad          | AWS IAM + AWS KMS + API Gateway API Keys + Usage Plans               |

---

## Estructura del Repositorio

```
prediccion-demanda-aws/
│
├── infrastructure/
│   ├── template.yaml                    # Infraestructura como código (SAM/CloudFormation)
│   └── samconfig.toml                   # Configuración SAM (stack, región, ECR auto)
│
├── src/
│   ├── etl/
│   │   ├── lambda_function.py           # Lambda ETL — trigger S3
│   │   └── etl_pipeline.py              # Script ETL completo
│   ├── inferencia/
│   │   ├── Dockerfile                   # Container Image del Lambda Inferencia (R5)
│   │   ├── lambda_function.py           # Handler de inferencia (carga modelo desde S3)
│   │   └── requirements.txt             # Dependencias Python del Lambda
│   └── training/                        # Código auxiliar para entrenamiento (R4)
│
├── notebooks/                           # Notebooks de modelado (R4)
│   ├── 01_eda.ipynb                     # Análisis exploratorio
│   ├── 02_baseline_ingenuo.ipynb        # Baseline por media histórica
│   ├── 03_linear_learner.ipynb          # Ridge Regression
│   ├── 04_xgboost_base.ipynb            # XGBoost out-of-the-box
│   ├── 05_xgboost_features.ipynb        # XGBoost + feature engineering
│   └── 06_xgboost_tuning.ipynb          # Tuning + modelo final + Model Artifact
│
├── scripts/
│   └── build_store_metadata.py          # Genera store_metadata.csv para inferencia (R5)
│
├── streamlit/                           # Dashboard cliente de la API (R5)
│   ├── dashboard.py                     # Aplicación Streamlit (2 pestañas)
│   ├── requirements.txt                 # Dependencias del dashboard
│   ├── README.md                        # Instrucciones de ejecución local
│   └── .streamlit/
│       └── secrets.toml.example         # Plantilla de secretos (API_URL + API_KEY)
│
├── results/                             # Métricas, gráficos y pruebas funcionales
│   ├── metrics_comparison.csv           # Comparativa de métricas por iteración (R4)
│   ├── tuning_results.csv               # Resultados del tuning de hiperparámetros (R4)
│   ├── worst_stores_test.csv            # Análisis de errores por tienda (R4)
│   ├── plots/                           # Gráficos generados (8 PNG)
│   └── api_tests/                       # 8 tests funcionales del despliegue (R5)
│
├── docs/                                # Informes en PDF y evidencias
│   ├── R2_arquitectura.pdf
│   ├── R3_etl.pdf
│   ├── R4_modelo.pdf
│   ├── informe_a5_ablascolo_prediccion_demanda_aws.pdf   # Informe R5
│   ├── r5_recursos_aws.txt              # Tabla de ARNs/recursos del stack
│   ├── r5_metricas_cloudwatch.txt       # Métricas reales del Lambda
│   └── screenshots/                     # 8 capturas de evidencia (R5)
│
├── data/
│   └── sample/
│       └── train_sample.csv             # Muestra del dataset (500 filas)
│
└── README.md
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
        ├── train.csv                                # Histórico de ventas (~1M filas, 38 MB)
        └── store.csv                                # Información de tiendas (1.115 filas)

s3://prediccion-demanda-processed-319501512128/
    ├── rossmann/
    │   ├── train_clean_YYYYMMDD_HHMMSS.csv          # Dataset limpio tras ETL
    │   └── splits/
    │       ├── train_YYYYMMDD_HHMMSS.csv            # 70% — entrenamiento
    │       ├── validation_YYYYMMDD_HHMMSS.csv       # 15% — selección de hiperparámetros
    │       ├── test_YYYYMMDD_HHMMSS.csv             # 15% — evaluación final
    │       └── scaler_params_YYYYMMDD_HHMMSS.json   # Parámetros del MinMaxScaler
    └── output/
        ├── model.joblib                             # Model Artifact (XGBoost serializado)
        └── store_metadata.csv                       # Metadata estática de 1115 tiendas (R5)

s3://prediccion-demanda-output-319501512128/
    └── predicciones/
        └── prediccion_{store_id}_{fecha}.json       # Predicciones individuales (R5)
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
   - Normalización MinMax de variables numéricas continuas
5. **Carga:** Escritura del dataset procesado y splits train/validation/test en S3 `/processed/rossmann/`

**Resultado del ETL ejecutado:**

- Filas entrada: 1.017.209
- Filas salida: 844.338
- Nulos restantes: 0
- Columnas finales: 20
- Splits: 591.036 train / 126.651 validation / 126.651 test

---

## Modelado de Machine Learning

El modelo se ha desarrollado en **AWS SageMaker Notebook Instance** (`ml.t3.medium`) siguiendo una metodología iterativa con cinco etapas claramente diferenciadas. Cada iteración se encuentra en un notebook independiente dentro de `notebooks/`, permitiendo trazar la mejora progresiva del modelo.

### Algoritmo elegido: XGBoost

**XGBoost** (Extreme Gradient Boosting) se ha seleccionado como algoritmo principal por cuatro razones: es el estándar de facto para datos tabulares, se entrena en segundos sobre instancias económicas, expone nativamente la importancia de cada feature, y se ajusta perfectamente a las restricciones del AWS Academy Learner Lab.

### Progresión por iteraciones

| Iteración | Modelo                                        | Split      | RMSPE      | RMSE        | MAE       |
| --------- | --------------------------------------------- | ---------- | ---------- | ----------- | --------- |
| 0         | Baseline ingenuo (media Store × DayOfWeek)    | Validation | 38.03%     | 1.850 €     | 1.326 €   |
| 1         | Ridge Regression                              | Validation | 59.08%     | 2.917 €     | 2.100 €   |
| 2         | XGBoost base                                  | Validation | 37.16%     | 1.628 €     | 1.139 €   |
| 3         | XGBoost + Feature Engineering                 | Validation | 33.62%     | 1.097 €     | 764 €     |
| 4         | XGBoost tuneado (mejor configuración)         | Validation | 33.62%     | 1.097 €     | 764 €     |
| **4**     | **Modelo final (re-entrenado con train+val)** | **Test**   | **14.83%** | **1.051 €** | **741 €** |

**Mejora total respecto al baseline ingenuo: +61.0%**

### Hallazgos clave

- **El feature engineering aporta más que el cambio de algoritmo:** la transición de XGBoost base a XGBoost+FE reduce RMSPE en un 9.5%.
- **`StoreDOW_Sales_mean` domina la importancia del modelo** con un 70.8% del gain. La media histórica de ventas por (tienda × día de la semana) es la señal más predictiva del dataset.
- **Ridge sirve como caso de estudio metodológico:** su empeoramiento del 55% respecto al baseline ilustra cómo un modelo lineal con codificación inadecuada de variables categóricas puede ser peor que no usar Machine Learning.

### Hiperparámetros del modelo final

| Hiperparámetro  | Valor              | Justificación                                     |
| --------------- | ------------------ | ------------------------------------------------- |
| `n_estimators`  | 200                | Más allá de 200 el modelo no mejora en validation |
| `max_depth`     | 6                  | Valores mayores producen sobreajuste              |
| `learning_rate` | 0.1                | Equilibrio entre velocidad y estabilidad          |
| `subsample`     | 1.0                | Sin submuestreo, dataset suficientemente grande   |
| `objective`     | `reg:squarederror` | Pérdida cuadrática para regresión                 |
| `tree_method`   | `hist`             | Más rápido para datasets grandes                  |

### Model Artifact

El modelo final está serializado con `joblib` y disponible en S3:

```
s3://prediccion-demanda-processed-319501512128/output/model.joblib
```

El artefacto contiene el modelo XGBoost entrenado, la lista de features ordenadas, las tablas de estadísticas históricas (`store_stats` y `store_dow_stats`) necesarias para enriquecer datos nuevos, los hiperparámetros óptimos y las métricas finales en test.

---

## Despliegue del modelo (Reto 5)

El modelo se expone como un servicio REST seguro y observable mediante una arquitectura serverless completamente gestionada con AWS SAM. Toda la lógica de inferencia vive en un Lambda empaquetado como Container Image que carga el `model.joblib` directamente desde S3.

### Arquitectura

```
Cliente (cURL / Postman / Streamlit)
   │ HTTPS + x-api-key
   ▼
API Gateway REST (Prod) ──► Lambda Inferencia (Container Image)
                              │  Python 3.12 + xgboost 3.2.0 + sklearn
                              │  1024 MB · 60s · 296 MB usados
                              │
                              ├──► DynamoDB (PrediccionesTable)
                              └──► S3 output/ (JSON por predicción)
                              ▲
                              │ joblib.load (cold start)
                              S3 processed (KMS):
                                model.joblib (1.2 MB)
                              + store_metadata.csv (77 KB)

CloudWatch ← logs + métricas de toda la cadena
ECR ← imagen Docker del Lambda Inferencia
```

### Endpoints expuestos

| Método | Path                          | Descripción                                              |
| ------ | ----------------------------- | -------------------------------------------------------- |
| POST   | `/prediccion`                 | Solicita una nueva predicción para (`store_id`, `fecha`) |
| GET    | `/predicciones/{store_id}`    | Devuelve el histórico de predicciones desde DynamoDB     |

Ambos endpoints requieren el header `x-api-key` con la API Key del Usage Plan. Sin ella, la API responde `403 Forbidden`.

### Reproducir el despliegue desde cero

```bash
git clone https://github.com/blasketch/prediccion-demanda-aws.git
cd prediccion-demanda-aws

# 1. Generar store_metadata.csv (única vez por cuenta AWS)
python3 scripts/build_store_metadata.py

# 2. Build + deploy de toda la infraestructura
cd infrastructure
sam build
sam deploy
```

SAM gestiona automáticamente la construcción de la imagen Docker, su publicación en ECR (creado automáticamente gracias a `resolve_image_repos = true`), y el despliegue de todos los recursos CloudFormation respetando las dependencias entre ellos.

### Consumir la API

```bash
# Obtener API Key, ID de la API y URL (una vez tras el deploy)
KEY_ID=$(aws cloudformation describe-stack-resources --stack-name prediccion-demanda \
  --query 'StackResources[?LogicalResourceId==`ApiGatewayApiKey`].PhysicalResourceId' --output text)
API_KEY=$(aws apigateway get-api-key --api-key $KEY_ID --include-value \
  --query 'value' --output text)
API_ID=$(aws apigateway get-rest-apis \
  --query 'items[?name==`prediccion-demanda-ApiGateway`].id' --output text)
API_URL=https://$API_ID.execute-api.us-east-1.amazonaws.com/Prod

# POST /prediccion — solicitar una predicción
curl -X POST -H "Content-Type: application/json" -H "x-api-key: $API_KEY" \
  -d '{"store_id": 1, "fecha": "2015-09-17", "promo": 1}' \
  $API_URL/prediccion

# Respuesta:
# {"store_id": 1, "fecha": "2015-09-17",
#  "prediccion_unidades": 4667.26,
#  "modelo": "xgboost-r4-final",
#  "rmspe_test": 0.1483}

# GET /predicciones/{store_id} — consultar histórico
curl -H "x-api-key: $API_KEY" $API_URL/predicciones/1
```

### Dashboard Streamlit (cliente local)

```bash
cd streamlit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar secrets.toml con los valores reales de API_URL y API_KEY
streamlit run dashboard.py
```

Abre <http://localhost:8501>. El dashboard tiene dos pestañas: **"Nueva predicción"** (formulario con inputs interactivos) e **"Histórico por tienda"** (consulta a DynamoDB).

### Resultados clave del despliegue

- **Latencia warm:** 47 ms (mediana, apta para uso interactivo)
- **Cold start:** ~10-15 s (descarga del modelo + imports xgboost/sklearn)
- **Memoria pico:** 296 MB de 1024 MB asignados (margen del 71%)
- **Errores:** 0 en toda la batería de tests
- **8 tests funcionales** documentados con input/output en [`results/api_tests/`](results/api_tests/)
- **Capturas de evidencia** en [`docs/screenshots/`](docs/screenshots/)
- **Métricas CloudWatch reales** en [`docs/r5_metricas_cloudwatch.txt`](docs/r5_metricas_cloudwatch.txt)

---

## Cómo reproducir el entrenamiento

Si quieres reproducir el modelado paso a paso:

1. **Levantar Notebook Instance** en SageMaker:
   - Tipo: `ml.t3.medium`
   - IAM role: `LabRole` (en AWS Academy)
   - Repositorio Git: clonar este repo automáticamente al crearla

2. **Instalar dependencias** desde un terminal de Jupyter:

```bash
   pip install seaborn
   conda install -y -c conda-forge xgboost
```

3. **Ejecutar los notebooks en orden** dentro de `notebooks/`:
   - `01_eda.ipynb` — análisis exploratorio y validación de splits
   - `02_baseline_ingenuo.ipynb` — establecer suelo de rendimiento
   - `03_linear_learner.ipynb` — primer modelo de ML (Ridge)
   - `04_xgboost_base.ipynb` — XGBoost out-of-the-box
   - `05_xgboost_features.ipynb` — feature engineering
   - `06_xgboost_tuning.ipynb` — tuning y modelo final

4. **El modelo entrenado** queda disponible en S3 (`output/model.joblib`) listo para inferencia.

---

## Recursos AWS desplegados

| Recurso              | Identificador                                                         |
| -------------------- | --------------------------------------------------------------------- |
| S3 Raw               | `prediccion-demanda-raw-319501512128`                                 |
| S3 Processed         | `prediccion-demanda-processed-319501512128`                           |
| S3 Output            | `prediccion-demanda-output-319501512128`                              |
| DynamoDB             | `PrediccionesTable`                                                   |
| Lambda ETL           | `prediccion-demanda-LambdaETL`                                        |
| Lambda Inferencia    | `prediccion-demanda-LambdaInferencia-R4RUpSndnGNp` (Container Image)  |
| API Gateway          | `36bjw4fzt5` · stage `Prod`                                           |
| API Key              | `z5xaw6tt1i` (Usage Plan: 1000 req/día, 100 RPS, burst 50)            |
| Usage Plan           | `tt8ivj`                                                              |
| ECR Repository       | `predicciondemand