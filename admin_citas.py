# admin_citas.py
import streamlit as st
from datetime import date
from db_utils import ensure_schema, listar_citas, cambiar_estado_cita

st.set_page_config(page_title="Citas - Admin", page_icon="🧑‍⚕️", layout="wide")
ensure_schema()

st.title("📒 Agenda de citas (Carmen)")

# PIN opcional desde secrets
pin_ok = True
ADMIN_PIN = st.secrets.get("ADMIN_PIN")
if ADMIN_PIN:
    inp = st.text_input("PIN admin", type="password")
    pin_ok = (inp == ADMIN_PIN)
    if not pin_ok:
        st.stop()

colf = st.columns(3)
with colf[0]:
    fecha = st.date_input("Fecha", value=date.today())
with colf[1]:
    profesional = st.selectbox("Profesional", ["Carmen"])
with colf[2]:
    estado = st.selectbox("Estado", ["(todos)", "reservada", "atendida", "cancelada"])
    estado = None if estado == "(todos)" else estado

rows = listar_citas(fecha=fecha, profesional=profesional, estado=estado)

if not rows:
    st.info("Sin citas para ese filtro.")
else:
    for (id_, nombre, tel, motivo, prof, fch, hr, est, created) in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2,1,1,2])
            c1.markdown(f"**{hr.strftime('%H:%M')} – {nombre}**")
            c1.caption(f"Motivo: {motivo or '—'}")
            c2.write(f"Estado: **{est}**")
            c3.write(f"Tel: {tel or '—'}")
            c4.write(f"Creada: {created.strftime('%d/%m %H:%M')}")

            b1, b2, b3 = st.columns(3)
            if b1.button("Marcar atendida", key=f"a-{id_}", disabled=(est=="atendida")):
                cambiar_estado_cita(id_, "atendida"); st.rerun()
            if b2.button("Cancelar", key=f"c-{id_}", disabled=(est=="cancelada")):
                cambiar_estado_cita(id_, "cancelada"); st.rerun()
            if b3.button("Reactivar", key=f"r-{id_}", disabled=(est=="reservada")):
                cambiar_estado_cita(id_, "reservada"); st.rerun()
