import streamlit as st
from datetime import date, datetime
import pandas as pd
from modules.core import (
    generar_slots, crear_cita_manual, citas_por_dia,
    actualizar_cita, eliminar_cita
)

st.set_page_config(page_title="Carmen — Panel", page_icon="🗂️", layout="wide")

if st.session_state.get("role") != "admin":
    st.switch_page("pages/0_Login.py")

st.title("🗂️ Panel de Carmen")

colf, colr = st.columns([1, 2], gap="large")

with colf:
    fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")

    opts_admin = [t.strftime("%H:%M") for t in generar_slots(fecha_sel)]
    slot = st.selectbox("Hora", opts_admin) if opts_admin else None
    if not opts_admin:
        st.info("Día no laborable o sin bloques disponibles.")

    nombre = st.text_input("Nombre paciente")
    tel    = st.text_input("Teléfono")
    nota   = st.text_area("Nota (opcional)")

    if st.button("➕ Crear cita"):
        if not slot:
            st.error("Selecciona un día con horarios disponibles.")
        elif not (nombre.strip() and tel.strip()):
            st.error("Nombre y teléfono son obligatorios.")
        else:
            crear_cita_manual(fecha_sel, datetime.strptime(slot, "%H:%M").time(), nombre, tel, nota or None)
            st.success("Cita creada."); st.rerun()

with colr:
    st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")
    df = citas_por_dia(fecha_sel)

    slots_list = generar_slots(fecha_sel)
    if slots_list:
        todos_slots = pd.DataFrame({"hora": slots_list})
        todos_slots["hora_txt"] = todos_slots["hora"].map(lambda t: t.strftime("%H:%M"))

        df_m = df.copy()
        if "hora" not in df_m.columns:
            df_m["hora"] = pd.NaT
        df_m["hora_txt"] = df_m["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)

        show = todos_slots.merge(df_m, on="hora_txt", how="left")
        show["estado"] = show["id_cita"].apply(lambda x: "✅ libre" if pd.isna(x) else "🟡 ocupado")
        cols = ["hora_txt", "estado", "id_cita", "paciente_id", "nombre", "telefono", "nota"]
        for c in cols:
            if c not in show.columns: show[c] = None
        st.dataframe(show[cols], use_container_width=True)
    else:
        st.info("Domingo (no laborable).")

    if df.empty:
        st.info("No hay citas ocupadas en este día.")
    else:
        st.divider(); st.caption("Editar / eliminar cita")
        ids = df["id_cita"].astype(int).tolist()
        cid = st.selectbox("ID cita", ids)
        r = df[df.id_cita == cid].iloc[0]

        nombre_e = st.text_input("Nombre", r["nombre"] or "", key="nombre_edit")
        tel_e    = st.text_input("Teléfono", r["telefono"] or "", key="tel_edit")
        nota_e   = st.text_area("Nota", r["nota"] or "", key="nota_edit")

        if st.button("💾 Guardar cambios"):
            if nombre_e.strip() and tel_e.strip():
                actualizar_cita(int(cid), nombre_e, tel_e, nota_e or None)
                st.success("Actualizado."); st.rerun()
            else:
                st.error("Nombre y teléfono son obligatorios.")

        st.divider(); st.caption("Eliminar cita")
        confirm = st.checkbox("Confirmar eliminación")
        if st.button("🗑️ Eliminar", disabled=not confirm):
            n = eliminar_cita(int(cid))
            st.success("Cita eliminada." if n else "La cita ya no existía.")
            st.rerun()
