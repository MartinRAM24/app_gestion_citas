# paciente_agendar.py
import streamlit as st
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from db_utils import ensure_schema, slots_del_dia, slots_ocupados, crear_cita

st.set_page_config(page_title="Agendar cita", page_icon="🗓️", layout="centered")
ensure_schema()  # crea/asegura tablas en Neon

st.title("🗓️ Agenda tu cita con Carmen")

MX = ZoneInfo("America/Mexico_City")
hoy_mx = datetime.now(MX).date()
min_day = hoy_mx + timedelta(days=2)  # siempre pasado mañana
profesional = "Carmen"

fecha_sel = st.date_input(
    "Fecha",
    min_value=min_day,
    value=min_day,
    help="Solo puedes agendar a partir de pasado mañana."
)

with st.form("form_agenda", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Tu nombre*", placeholder="Nombre y Apellido")
    with col2:
        telefono = st.text_input("Teléfono (opcional)", placeholder="55 1234 5678")
    motivo = st.text_area("Motivo / Nota (opcional)")

    ocupados = slots_ocupados(fecha_sel, profesional)
    todos = slots_del_dia(fecha_sel)
    disponibles = [h for h in todos if h not in ocupados]

    if not disponibles:
        st.info("No hay horarios disponibles en esa fecha. Prueba otro día. 🙏")
        submit = st.form_submit_button("Agendar", disabled=True)
    else:
        slot = st.selectbox("Horario disponible", disponibles, format_func=lambda t: t.strftime("%H:%M"))
        submit = st.form_submit_button("Agendar")

    if submit:
        # Blindaje por si manipulan el front
        if fecha_sel < (datetime.now(MX).date() + timedelta(days=2)):
            st.error("No puedes agendar para hoy ni mañana. Elige otra fecha.")
            st.stop()
        if not nombre.strip():
            st.error("Por favor, escribe tu nombre.")
            st.stop()
        try:
            _ = crear_cita(nombre.strip(), telefono.strip(), motivo.strip(), fecha_sel, slot, profesional)
            st.success(f"¡Listo {nombre}! Tu cita quedó para **{fecha_sel.strftime('%A %d/%m/%Y')} a las {slot.strftime('%H:%M')}**.")
            st.caption("Si necesitas cambiarla o cancelarla, avísanos con tiempo. 💜")
        except Exception:
            st.error("Ese horario se acaba de ocupar. Elige otro, por favor.")
