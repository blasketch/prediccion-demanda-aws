# Dashboard Streamlit predicción de demanda

Cliente visual que consume la API REST desplegada en AWS.

## Setup local

1. Instalar dependencias:
```bash
   pip install -r requirements.txt
```
2. Copiar la plantilla de secrets y rellenar:
```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Editar .streamlit/secrets.toml con los valores reales de API_URL y API_KEY
```
3. Lanzar:
```bash
   streamlit run dashboard.py
```
4. Abrir <http://localhost:8501> en el navegador.

## Funcionalidad

- **Tab 1 (Nueva predicción)**: formulario con `store_id`, `fecha`, `promo`,
  `state_holiday`, `school_holiday`. Devuelve la predicción de ventas en €.
- **Tab 2 (Histórico)**: consulta las predicciones almacenadas en DynamoDB
  para una tienda dada.
