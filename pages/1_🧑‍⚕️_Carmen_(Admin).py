import streamlit as st
from datetime import date, datetime
from app_gestion_citas.db_utils import (
    ensure_schema, generar_slots, citas_por_dia, crear_cita_manual, actualizar_cita
)
from app_gestion_citas.constants import BLOQUEO_DIAS_MIN

st.set_page_config(page_title="Carmen — Admin", page_icon="🧑‍⚕️", layout="wide")
ensure_schema()

st.header("🧑‍⚕️ Panel de Carmen")

colf, colr = st.columns([1, 2])

with colf:
    fecha_sel = st.date_input("Día", value=date.today())
    st.caption("Puedes crear citas manualmente (sin restricción de 3 días).")

    slot = st.selectbox("Hora", [t.strftime('%H:%M') for t in generar_slots(fecha_sel)])
    nombre = st.text_input("Nombre paciente")
    tel = st.text_input("Teléfono")
    nota = st.text_area("Nota (opcional)")

    if st.button("➕ Crear cita"):
        if nombre.strip() and tel.strip():
            crear_cita_manual(
                fecha_sel,
                datetime.strptime(slot, '%H:%M').time(),
                nombre,
                tel,
                nota or None
            )
            st.success("Cita creada.")
            st.rerun()
        else:
            st.error("Nombre y teléfono son obligatorios.")

with colr:
    st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")
    df = citas_por_dia(fecha_sel)

    if df.empty:
        st.info("No hay citas aún.")
    else:
        st.dataframe(df, use_container_width=True)
        st.divider()
        st.caption("Editar cita seleccionada")

        ids = df["id"].astype(int).tolist()
        cid = st.selectbox("ID cita", ids)
        r = df[df.id == cid].iloc[0]

        nombre_e = st.text_input("Nombre", r["nombre"] or "")
        tel_e = st.text_input("Teléfono", r["telefono"] or "")
        nota_e = st.text_area("Nota", r["nota"] or "")

        if st.button("💾 Guardar cambios"):
            if nombre_e.strip() and tel_e.strip():
                actualizar_cita(int(cid), nombre_e, tel_e, nota_e or None)
                st.success("Actualizado.")
                st.rerun()
            else:
                st.error("Nombre y teléfono son obligatorios.")
