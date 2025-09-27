import streamlit as st
from app_gestion_citas.db_utils import ensure_schema

st.set_page_config(page_title="Gestión de Citas - Carmen", page_icon="🩺", layout="wide")

ensure_schema()

st.title("Aplicación para gestionar citas — Carmen")

st.markdown(
    """
- **Base de datos**: Neon Postgres + `psycopg`  
- **Frontend**: Streamlit multipágina  

Usa el menú de la izquierda o los enlaces rápidos:
    """
)

# Enlaces rápidos (solo si tu versión de Streamlit es >=1.31)
try:
    st.page_link("pages/2_📅_Agendar_(Pacientes).py", label="📅 Agendar (Pacientes)")
    st.page_link("pages/1_🧑‍⚕️_Carmen_(Admin).py", label="🧑‍⚕️ Carmen (Admin)")
except AttributeError:
    st.info("Navega con el menú lateral (actualiza Streamlit para usar enlaces rápidos).")
