import streamlit as st
from datetime import date, datetime, timedelta
from modules.core import (
    generar_slots, slots_ocupados, agendar_cita_autenticado,
    proxima_cita_paciente, is_fecha_permitida, BLOQUEO_DIAS_MIN
)

st.set_page_config(page_title="Paciente — Agenda", page_icon="📅", layout="wide")

if st.session_state.get("role") != "paciente" or not st.session_state.get("paciente"):
    st.switch_page("pages/0_Login.py")

p = st.session_state.paciente
pid = int(p["id"])

st.title(f"👋 Hola, {p['nombre']}")

# --- Próxima cita
st.subheader("📌 Tu próxima cita")
next_df = proxima_cita_paciente(pid)
if next_df.empty:
    st.info("Aún no tienes una próxima cita agendada.")
else:
    r = next_df.iloc[0]
    st.success(f"**Fecha:** {r['fecha']} — **Hora:** {str(r['hora'])[:5]}  \n**Nota:** {r.get('nota') or '—'}")

# --- Agendar
st.subheader("📅 Agendar nueva cita")
min_day = date.today() + timedelta(days=BLOQUEO_DIAS_MIN)
fecha = st.date_input("Día (disponible desde el tercer día)", value=min_day, min_value=min_day)

if not is_fecha_permitida(fecha):
    st.error("Solo puedes agendar a partir del tercer día.")
else:
    libres = [t for t in generar_slots(fecha) if t not in slots_ocupados(fecha)]
    slot = st.selectbox("Horario", [t.strftime("%H:%M") for t in libres]) if libres else None
    if not libres:
        st.warning("No hay horarios libres en este día.")

    nota = st.text_area("Motivo/nota (opcional)")
    if st.button("Confirmar cita", disabled=(slot is None)):
        try:
            h = datetime.strptime(slot, "%H:%M").time()
            agendar_cita_autenticado(fecha, h, paciente_id=pid, nota=nota or None)
            st.success("¡Cita agendada! ✨")
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.divider()
if st.button("🚪 Cerrar sesión"):
    st.session_state.role = None
    st.session_state.paciente = None
    st.switch_page("pages/0_Login.py")
