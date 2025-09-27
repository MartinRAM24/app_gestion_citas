# app_home.py
import streamlit as st
from db_utils import ensure_schema

st.set_page_config(page_title="Citas", page_icon="🗓️", layout="centered")
ensure_schema()

st.title("Citas con Carmen")
st.page_link("paciente_agendar.py", label="🗓️ Agendar (Pacientes)", icon="🧑‍⚕️")
st.page_link("admin_citas.py", label="📒 Agenda (Carmen)", icon="🗃️")
st.caption("Regla: solo se puede reservar a partir de pasado mañana.")
