import streamlit as st
from modules.core import is_admin_ok, login_paciente, registrar_paciente, normalize_tel

st.set_page_config(page_title="Ingreso", page_icon="🩺", layout="wide")

st.title("🩺 Gestión de Citas")
st.caption("Bienvenida/o. Elige cómo quieres entrar.")

# Estado base
st.session_state.setdefault("role", None)
st.session_state.setdefault("paciente", None)

tab_admin, tab_pac = st.tabs(["👩‍⚕️ Coach", "🧑 Paciente"])

# ---- Coach
with tab_admin:
    st.subheader("Carmen (Coach)")
    with st.form("form_admin"):
        u = st.text_input("Usuario", value="carmen", disabled=True)
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar como Coach")
    if ok:
        if is_admin_ok(u, p):
            st.session_state.role = "admin"
            st.switch_page("pages/2_Carmen_Admin.py")
        else:
            st.error("Credenciales inválidas.")

# ---- Paciente
with tab_pac:
    st.subheader("Paciente")
    modo = st.radio("Cuenta", ["Iniciar sesión", "Registrarme"], horizontal=True, key="pac_modo")

    if modo == "Iniciar sesión":
        with st.form("form_login"):
            tel = st.text_input("Teléfono")
            pw  = st.text_input("Contraseña", type="password")
            ok  = st.form_submit_button("Entrar")
        if ok:
            user = login_paciente(tel, pw)
            if user:
                st.session_state.role = "paciente"
                st.session_state.paciente = user
                st.switch_page("pages/1_Paciente_Dashboard.py")
            else:
                st.error("Teléfono o contraseña incorrectos.")
    else:
        with st.form("form_reg"):
            nombre = st.text_input("Nombre completo")
            tel    = st.text_input("Teléfono")
            pw1    = st.text_input("Contraseña", type="password")
            pw2    = st.text_input("Repite tu contraseña", type="password")
            ok     = st.form_submit_button("Registrarme")
        if ok:
            if not (nombre.strip() and tel.strip() and pw1 and pw2):
                st.error("Completa todos los campos.")
            elif pw1 != pw2:
                st.error("Las contraseñas no coinciden.")
            else:
                pid = registrar_paciente(nombre, tel, pw1)
                st.session_state.role = "paciente"
                st.session_state.paciente = {"id": pid, "nombre": nombre.strip(), "telefono": normalize_tel(tel)}
                st.switch_page("pages/1_Paciente_Dashboard.py")
