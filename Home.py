# app.py — Router condicional (requiere Streamlit >= 1.41 para st.Page/st.navigation)
import streamlit as st

st.set_page_config(page_title="Citas — Carmen", page_icon="🩺", layout="wide")

# Estado base
st.session_state.setdefault("role", None)
st.session_state.setdefault("paciente", None)

# Define páginas
home      = st.Page("pages/0_Login.py",              title="Inicio",                icon="🩺")
pac_dash  = st.Page("pages/1_Paciente_Dashboard.py", title="Paciente — Agenda",     icon="📅")
adm_panel = st.Page("pages/2_Carmen_Admin.py",       title="Carmen — Panel",        icon="🗂️")

role = st.session_state["role"]

if role == "paciente":
    nav = st.navigation([pac_dash])
elif role == "admin":
    nav = st.navigation([adm_panel])
else:
    nav = st.navigation([home])

nav.run()





