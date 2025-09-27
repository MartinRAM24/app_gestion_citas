import streamlit as st
from datetime import date, datetime, timedelta
from app_gestion_citas.db_utils import (
    generar_slots, slots_ocupados, agendar_cita, ensure_schema, is_fecha_permitida
)
from app_gestion_citas.constants import BLOQUEO_DIAS_MIN
# --- FIX para imports en Streamlit Cloud desde /pages ---
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))  # sube de /pages a raíz
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ---------------------------------------------------------


st.set_page_config(page_title="Agendar — Pacientes", page_icon="📅", layout="wide")
ensure_schema()

st.header("📅 Agenda tu cita")

# hoy y mañana bloqueados → se puede desde el tercer día
min_day = date.today() + timedelta(days=BLOQUEO_DIAS_MIN)
fecha = st.date_input(
    "Elige el día (disponible desde el tercer día)",
    value=min_day,
    min_value=min_day
)

if not is_fecha_permitida(fecha):
    st.error("Solo puedes agendar a partir del tercer día.")
    st.stop()

ocupados = slots_ocupados(fecha)

# Construye opciones (muestra libre/ocupado)
slots_txt = []
for t in generar_slots(fecha):
    label = t.strftime('%H:%M')
    libre = t not in ocupados
    slots_txt.append(f"{label} {'— ✅ libre' if libre else '— ❌ ocupado'}")

st.write("Selecciona un horario que esté marcado como **libre**:")
slot_sel = st.selectbox("Horario", options=slots_txt, index=0)

nombre = st.text_input("Tu nombre")
telefono = st.text_input("Tu teléfono")
nota = st.text_area("Motivo o nota (opcional)")

if st.button("📝 Confirmar cita"):
    hora_txt = slot_sel.split(' ')[0]  # toma "HH:MM" antes del texto "— ..."
    hora = datetime.strptime(hora_txt, '%H:%M').time()
    if hora in ocupados:
        st.error("Ese horario acaba de ocuparse, intenta con otro.")
    elif not (nombre.strip() and telefono.strip()):
        st.error("Nombre y teléfono son obligatorios.")
    else:
        try:
            agendar_cita(fecha, hora, nombre, telefono, nota or None)
            st.success("¡Cita agendada! Te esperamos ✨")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo agendar: {e}")
