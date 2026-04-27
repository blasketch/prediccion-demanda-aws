# Predicción de demanda para E-commerce en AWS

Pipeline completo de predicción de demanda diaria por tienda para empresas de comercio electrónico, desplegado sobre servicios gestionados de AWS. Incluye infraestructura como código, ETL automatizado y un modelo XGBoost entrenado con feature engineering avanzado.

> **Resultado del modelo final:** RMSPE de **14.83%** en test, una mejora del **61%** respecto al baseline ingenuo. Modelo serializado y disponible en S3 como Model Artifact reutilizable.

---

## Descripción del Proyecto

Las empresas de e-commerce pierden millones de euros anualmente por sobrestock y desabastecimiento. Este proyecto automatiza la **predicción de ventas diarias por tienda**, proporcionando a los equipos de compras y logística una estimación cuantitativa y reproducible basada en el histórico de ventas.

**Objetivos:**

- Reducir el exceso de inventario entre un 20% y un 30%
- Elevar la tasa de disponibilidad de producto por encima del 95%
- Automatizar el proceso de predicción sin intervención manual

## Arquitectura AWS

El sistema está organizado en ocho zonas funcionales desplegadas sobre AWS:

| Zona               | Servicios                                                 |
| ------------------ | --------------------------------------------------------- |
| Ingesta de datos   | Amazon S3 (Raw Data)                                      |
| Procesamiento      | AWS Lambda (trigger) + SageMaker Processing Job           |
| ML / Entrenamiento | SageMaker Notebook Instance + Amazon S3 (Model Artifacts) |
| Inferencia         | SageMaker Endpoint + AWS Lambda + Amazon API Gateway      |
| Persistencia       | Amazon DynamoDB + Amazon S3 (Predictions)                 |
| Visualización      | Streamlit                                                 |
| Observabilidad     | Amazon CloudWatch + AWS CloudTrail                        |
| Seguridad          | AWS IAM + AWS KMS                                         |

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
│   │   ├── lambda_function.py           # Lambda ETL — trigger S3
│   │   └── etl_pipeline.py              # Script ETL completo
│   ├── inferencia/
│   │   └── lambda_function.py           # Lambda Inferencia — API Gateway
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
├── results/                             # Métricas y gráficos del modelado (R4)
│   ├── metrics_comparison.csv           # Comparativa de métricas por iteración
│   ├── tuning_results.csv               # Resultados del tuning de hiperparámetros
│   ├── worst_stores_test.csv            # Análisis de errores por tienda
│   └── plots/                           # Gráficos generados (8 PNG)
│
├── docs/                                # Informes en PDF
│   ├── R2_arquitectura.pdf
│   ├── R3_etl.pdf
│   └── R4_modelo.pdf
│
├── streamlit/
│   └── dashboard.py                     # Dashboard de visualización
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
        └── model.joblib                             # Model Artifact (XGBoost serializado)

s3://prediccion-demanda-output-319501512128/
    └── predicciones/
        └── predicciones_YYYYMMDD.csv                # Predicciones generadas por el modelo
```

---

## Pipeline ETL

El proceso ETL se ejecuta mediante el script `src/etl/etl_pipeline.py`, invocado desde CloudShell o SageMaker Processing Job. La función Lambda (`src/etl/lambda_function.py`) actúa como **trigger**, detectando automáticamente nuevos archivos subidos al bucket raw y orquestando el proceso.

**Flujo completo:**

1. **Trigger:** Se sube un CSV al bucket S3 raw -- Lambda detecta el evento `ObjectCreated`
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
- **`StoreDOW_Sales_mean` domina la importancia del modelo** con un 70.8% del gain. La media histórica de ventas por (tienda x día de la semana) es la señal más predictiva del dataset.
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

El artefacto contiene el modelo XGBoost entrenado, la lista de features ordenadas, las tablas de estadísticas históricas (`store_stats` y `store_dow_stats`) necesarias para enriquecer datos nuevos, los hiperparámetros óptimos y las métricas finales en test. Está listo para ser consumido por el pipeline de inferencia.

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
   - `01_eda.ipynb`  análisis exploratorio y validación de splits
   - `02_baseline_ingenuo.ipynb`  establecer suelo de rendimiento
   - `03_linear_learner.ipynb`  primer modelo de ML (Ridge)
   - `04_xgboost_base.ipynb`  XGBoost out-of-the-box
   - `05_xgboost_features.ipynb`  feature engineering
   - `06_xgboost_tuning.ipynb`  tuning y modelo final
4. **El modelo entrenado** queda disponible en S3 (`output/model.joblib`) listo para inferencia.

---

## Recursos AWS desplegados

| Recurso            | Nombre                                    | ARN                                                                                  |
| ------------------ | ----------------------------------------- | ------------------------------------------------------------------------------------ |
| S3 Raw             | prediccion-demanda-raw-319501512128       | `arn:aws:s3:::prediccion-demanda-raw-319501512128`                                   |
| S3 Processed       | prediccion-demanda-processed-319501512128 | `arn:aws:s3:::prediccion-demanda-processed-319501512128`                             |
| S3 Output          | prediccion-demanda-output-319501512128    | `arn:aws:s3:::prediccion-demanda-output-319501512128`                                |
| DynamoDB           | PrediccionesTable                         | `arn:aws:dynamodb:us-east-1:319501512128:table/PrediccionesTable`                    |
| Lambda ETL         | prediccion-demanda-LambdaETL              | `arn:aws:lambda:us-east-1:319501512128:function:prediccion-demanda-LambdaETL`        |
| Lambda Inferencia  | prediccion-demanda-LambdaInferencia       | `arn:aws:lambda:us-east-1:319501512128:function:prediccion-demanda-LambdaInferencia` |
| SageMaker Notebook | notebook-r4-prediccion-demanda            | Instance type `ml.t3.medium`, IAM role `LabRole`                                     |

---

## Tecnologías utilizadas

- **Python 3.12** — lenguaje principal
- **Pandas** — procesamiento y limpieza de datos
- **NumPy** — cálculo numérico y operaciones vectorizadas
- **Scikit-learn** — preprocesamiento, métricas y baseline lineal
- **XGBoost** — modelo de predicción principal
- **Matplotlib + Seaborn** — visualización de resultados
- **Joblib** — serialización del Model Artifact
- **Boto3** — SDK de AWS para Python
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

## Documentación

Los informes completos de cada actividad académica se encuentran en `docs/`:

- **R2** — Diseño de la arquitectura AWS
- **R3** — Pipeline ETL y preparación de datos
- **R4** — Entrenamiento del modelo de Machine Learning

---

## Autor

**Adrián Blasco Lozano**
Máster en Inteligencia Artificial — UOC
