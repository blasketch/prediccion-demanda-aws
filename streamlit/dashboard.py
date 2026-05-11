"""
Dashboard Streamlit para predicción de demanda Rossmann.
Consume la API REST desplegada en AWS.

"""
import streamlit as st
import requests
import pandas as pd
from datetime import date

# Config
st.set_page_config(
    page_title="Predicción Demanda Rossmann",
    page_icon="📊",
    layout="wide",
)

API_URL = st.secrets["API_URL"]
API_KEY = st.secrets["API_KEY"]

HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
}

# Header
st.title("Predicción de Demanda — Rossmann Stores")
st.markdown(
    "**Sistema de predicción de ventas diarias por tienda.**  \n"
    "Modelo: XGBoost (RMSPE 14.83 % en test) · "
    "Arquitectura: API Gateway + Lambda + DynamoDB"
)

# Sidebar
with st.sidebar:
    st.header("ℹ️ Sobre el sistema")
    st.markdown(
        """
        **Modelo desplegado**  
        - Algoritmo: XGBoost (`n_est=200, depth=6, lr=0.1`)  
        - Features: 30 (incl. estadísticas históricas por tienda y día semana)  
        - RMSPE test: **14,83 %**  
        - Mejora vs baseline ingenuo: **+61 %**  

        **Infraestructura AWS**  
        - Lambda (Container Image, 1 GB RAM)  
        - API Gateway REST (HTTPS + API Key)  
        - DynamoDB (persistencia de predicciones)  
        - S3 + KMS (model artifact cifrado)  
        - CloudWatch (logs + métricas)  

        **Seguridad**  
        - HTTPS obligatorio (rechaza HTTP)  
        - API Key requerida en cada llamada  
        - Usage Plan: 1000 req/día, 100 RPS  
        - IAM via LabRole (entorno Learner Lab)
        """
    )
    st.markdown("---")
    st.caption(f"Endpoint: `{API_URL}`")

# Tabs
tab1, tab2 = st.tabs(["🔮 Nueva predicción", "📈 Histórico por tienda"])

# TAB 1: Predicción
with tab1:
    st.subheader("Solicitar predicción")

    col1, col2 = st.columns(2)
    with col1:
        store_id = st.number_input(
            "ID de Tienda",
            min_value=1, max_value=1115, value=1, step=1,
            help="Tiendas disponibles: 1 a 1115",
        )
        fecha = st.date_input(
            "Fecha objetivo",
            value=date(2015, 9, 17),
            help="Fecha para la que predecir ventas",
        )
    with col2:
        promo = st.toggle("Promoción activa", value=True)
        state_holiday = st.selectbox(
            "Festivo estatal",
            options=[0, 1, 2, 3],
            format_func=lambda x: {0: "Ninguno", 1: "Público", 2: "Pascua", 3: "Navidad"}[x],
        )
        school_holiday = st.toggle("Vacaciones escolares", value=False)

    if st.button("🎯 Predecir", type="primary", use_container_width=True):
        payload = {
            "store_id": int(store_id),
            "fecha": fecha.strftime("%Y-%m-%d"),
            "promo": int(promo),
            "state_holiday": int(state_holiday),
            "school_holiday": int(school_holiday),
        }
        with st.spinner("Consultando modelo en AWS..."):
            try:
                resp = requests.post(
                    f"{API_URL}/prediccion",
                    headers=HEADERS, json=payload, timeout=35,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.success("✅ Predicción realizada")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Ventas predichas", f"{data['prediccion_unidades']:,.2f} €")
                    c2.metric("Tienda", f"#{data['store_id']}")
                    c3.metric("Fecha", data["fecha"])
                    st.caption(
                        f"Modelo: `{data['modelo']}` · "
                        f"RMSPE test: {data['rmspe_test']*100:.2f} %"
                    )
                    with st.expander("Ver request / response completos"):
                        st.json({"request": payload, "response": data})
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except requests.exceptions.Timeout:
                st.error("⏰ Timeout (>35s). Probable cold start, vuelve a intentar.")
            except Exception as e:
                st.error(f"❌ Error: {e}")

# TAB 2: Histórico
with tab2:
    st.subheader("Histórico de predicciones desde DynamoDB")

    col1, col2 = st.columns([3, 1])
    store_id_hist = col1.number_input(
        "ID de Tienda", min_value=1, max_value=1115, value=1, step=1, key="hist",
    )
    col2.write(""); col2.write("")
    if col2.button("🔍 Consultar", use_container_width=True):
        with st.spinner("Consultando DynamoDB..."):
            try:
                resp = requests.get(
                    f"{API_URL}/predicciones/{store_id_hist}",
                    headers=HEADERS, timeout=10,
                )
                if resp.status_code == 200:
                    items = resp.json().get("predicciones", [])
                    if not items:
                        st.info(f"Sin predicciones para la tienda {store_id_hist}")
                    else:
                        df = pd.DataFrame(items)
                        df["Prediccion"] = df["Prediccion"].astype(float)
                        df = df.sort_values("Timestamp", ascending=False)
                        st.success(f"📊 {len(items)} predicción(es) encontrada(s)")
                        st.dataframe(
                            df[["Fecha", "Prediccion", "Timestamp"]].rename(columns={
                                "Fecha": "Fecha predicción",
                                "Prediccion": "Ventas predichas (€)",
                                "Timestamp": "Generado en",
                            }),
                            use_container_width=True, hide_index=True,
                        )
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Footer
st.markdown("---")
st.caption(
    "Adrián Blasco Lozano · UOC · Reto 5: Despliegue y visualización"
)
