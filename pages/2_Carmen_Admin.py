from datetime import date, datetime

import pandas as pd
import streamlit as st

from modules.core import (
    crear_cita_manual,
    crear_cita_para_paciente,
    citas_por_dia,
    eliminar_cita,
    generar_slots,
    listar_pacientes,
    actualizar_cita,
    enviar_recordatorios_manana,
    whatsapp_status,
)

st.set_page_config(page_title="Carmen — Panel", page_icon="🗂️", layout="wide")

# --- Guard: requiere sesión de admin ---
if st.session_state.get("role") != "admin":
    st.session_state.role = None
    st.session_state.paciente = None
    try:
        st.switch_page("pages/0_Login.py")
    except Exception:
        st.rerun()

CUSTOM_CSS = """
/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #7B1E3C 0%, #800020 100%);
  color: #FFFFFF;
}
[data-testid="stSidebar"] * { color: #FFFFFF !important; }

/* Área principal en blanco */
main.block-container {
  background: #FFFFFF;
  padding-top: 1.2rem;
  padding-bottom: 3rem;
  border-radius: 12px;
}

/* Tarjetas internas (expanders, tabs, forms) */
section[data-testid="stSidebarNav"] { background: transparent; }

/* ===== Expanders ===== */
div[data-testid="stExpander"] > details {
  background: #2B2F36 !important;
  border: 1px solid #3A3F47 !important;
  border-radius: 12px !important;
}
div[data-testid="stExpander"] > details[open] { background: #2F343C !important; }
div[data-testid="stExpander"] summary {
  background: #2B2F36 !important;
  color: #EAECEF !important;
  border-radius: 12px !important;
}

/* ===== Inputs ===== */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[role="combobox"],
[data-testid="stFileUploader"] section[data-testid="stFileDropzone"] {
  background: #2F3136 !important;
  color: #F5F6F7 !important;
  border: 1px solid #4A4D55 !important;
  border-radius: 10px !important;
}

/* Placeholders */
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder,
[data-testid="stDateInput"] input::placeholder,
[data-testid="stTimeInput"] input::placeholder {
  color: #B8B9BE !important;
}

/* Desplegable del select */
div[data-baseweb="popover"] div[role="listbox"] {
  background: #2F3136 !important;
  color: #F5F6F7 !important;
  border: 1px solid #4A4D55 !important;
}

/* Botones primarios */
button[kind="primary"] {
  background: #800020 !important;
  color: #FFFFFF !important;
  border-radius: 10px !important;
  border: 0 !important;
}
button[kind="primary"]:hover { filter: brightness(0.9); }

/* Links */
a, .stLinkButton button { color: #7B1E3C !important; }

/* DataFrames */
.stDataFrame div[data-testid="stTable"] { border-radius: 10px; overflow: hidden; }

div[data-baseweb="notification"] { background-color: #800020 !important; color: #FFFFFF !important; }

/* Encabezados */
h1, h2, h3, h4 { color: #111827; }
"""
st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

st.title("🗂️ Panel de Carmen")

# 1) Día seleccionado y citas del día
fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")
df_dia = citas_por_dia(fecha_sel)

def _s(x):
    return (x or "").strip()

colf, colr = st.columns([1, 2], gap="large")

with colf:
    opts_admin = [t.strftime("%H:%M") for t in generar_slots(fecha_sel)]
    slot = st.selectbox("Hora", opts_admin, key="hora_admin") if opts_admin else None
    if not opts_admin:
        st.info("Día no laborable o sin bloques disponibles.")

    # Paciente: buscador
    df_pac = listar_pacientes(None)
    values = [0]
    labels_map = {0: "🔎 Buscar/seleccionar paciente registrado…"}
    if not df_pac.empty:
        for _, r in df_pac.iterrows():
            pid = int(r["id"])
            tel_v = (r.get("telefono") or "")
            tel_txt = f" · {tel_v}" if tel_v else ""
            labels_map[pid] = f"{r['nombre']}{tel_txt} · (ID {pid})"
            values.append(pid)

    sel_val = st.selectbox(
        "Paciente (puedes escribir para buscar)",
        options=values,
        index=0,
        key="pac_sel",
        format_func=lambda v: labels_map.get(v, "—"),
        help="Escribe parte del nombre o teléfono para filtrar. Si lo dejas en la primera opción, crea uno nuevo abajo.",
    )
    sel_id = None if sel_val == 0 else sel_val

    nombre_def, tel_def = "", ""
    if sel_id is not None and not df_pac.empty:
        r0 = df_pac.loc[df_pac["id"] == sel_id]
        if not r0.empty:
            r0 = r0.iloc[0]
            nombre_def = r0.get("nombre") or ""
            tel_def = r0.get("telefono") or ""

    nombre_nuevo = st.text_input(
        "Nombre del paciente (si es nuevo)",
        value=nombre_def,
        placeholder="Escribe el nombre SOLO si no seleccionaste uno registrado",
        key="nombre_nuevo",
    )
    tel = st.text_input("Teléfono (opcional)", value=tel_def, placeholder="Puedes dejarlo vacío", key="tel_nuevo")
    nota = st.text_area("Nota (opcional)", key="nota_nueva")

    # Choque de horario
    ocupado, nombre_ocupa = False, None
    if slot and not df_dia.empty and "hora" in df_dia.columns:
        df_tmp = df_dia.copy()
        df_tmp["hora_txt"] = df_tmp["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)
        fila_slot = df_tmp[df_tmp["hora_txt"] == slot]
        if not fila_slot.empty and fila_slot["id_cita"].notna().any():
            ocupado = True
            nombre_ocupa = fila_slot.iloc[0].get("nombre")

    if st.button("➕ Crear cita", key="btn_crear"):
        if not slot:
            st.error("Selecciona un día con horarios disponibles.")
        elif ocupado:
            detalle = f" por {nombre_ocupa}" if _s(nombre_ocupa) else ""
            st.error(f"Ya existe una cita a las {slot}{detalle}. Elige otra hora.")
        else:
            try:
                h = datetime.strptime(slot, "%H:%M").time()
                if sel_id is not None:
                    crear_cita_para_paciente(fecha_sel, h, sel_id, _s(nota) or None)
                else:
                    if not _s(nombre_nuevo):
                        st.error("Escribe el nombre del paciente (o selecciona uno registrado arriba).")
                        st.stop()
                    crear_cita_manual(fecha_sel, h, _s(nombre_nuevo), _s(tel), _s(nota) or None)
                st.success("Cita creada.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo crear la cita: {e}")

with colr:
    st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")
    slots_list = generar_slots(fecha_sel)
    if slots_list:
        todos_slots = pd.DataFrame({"hora": slots_list})
        todos_slots["hora_txt"] = todos_slots["hora"].map(lambda t: t.strftime("%H:%M"))

        df_m = df_dia.copy()
        if "hora" not in df_m.columns:
            df_m["hora"] = pd.NaT
        df_m["hora_txt"] = df_m["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)

        show = todos_slots.merge(df_m, on="hora_txt", how="left")
        show["estado"] = show["id_cita"].apply(lambda x: "✅ libre" if pd.isna(x) else "🟡 ocupado")
        cols = ["hora_txt", "estado", "id_cita", "paciente_id", "nombre", "telefono", "nota"]
        for c in cols:
            if c not in show.columns:
                show[c] = None
        st.dataframe(show[cols], use_container_width=True)
    else:
        st.info("Domingo (no laborable).")

    if df_dia.empty:
        st.info("No hay citas ocupadas en este día.")
    else:
        st.divider()
        st.caption("Editar / eliminar cita")
        ids = df_dia["id_cita"].astype(int).tolist()
        cid = st.selectbox("ID cita", ids, key="cid_edit")
        r = df_dia[df_dia.id_cita == cid].iloc[0]

        nombre_e = st.text_input("Nombre", (r.get("nombre") or ""), key="nombre_edit")
        tel_e = st.text_input("Teléfono (opcional)", (r.get("telefono") or ""), key="tel_edit", placeholder="Puede quedar vacío")
        nota_e = st.text_area("Nota", (r.get("nota") or ""), key="nota_edit")

        if st.button("💾 Guardar cambios", key="btn_guardar"):
            if _s(nombre_e):
                try:
                    actualizar_cita(int(cid), _s(nombre_e), (_s(tel_e) or None), (_s(nota_e) or None))
                    st.success("Actualizado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo actualizar la cita: {e}")
            else:
                st.error("El nombre es obligatorio.")

        st.divider()
        st.caption("Eliminar cita")
        confirm = st.checkbox("Confirmar eliminación", key="chk_del")
        if st.button("🗑️ Eliminar", disabled=not confirm, key="btn_del"):
            try:
                n = eliminar_cita(int(cid))
                st.success("Cita eliminada." if n else "La cita ya no existía.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar la cita: {e}")

# --------- RECORDATORIOS WHATSAPP (OPCIONAL) ----------
st.divider()
st.subheader("🔔 Recordatorios de WhatsApp (citas de mañana)")

wa_ok, wa_missing = whatsapp_status()
if not wa_ok:
    st.info(f"WhatsApp no está configurado (faltan: {', '.join(wa_missing)}). Esta sección es opcional.")

colA, _ = st.columns([1, 3])
with colA:
    dry = st.checkbox("Modo simulación (no envía)", value=True, key="dry_wa")

if st.button("📨 Enviar recordatorios de mañana", key="btn_wa", disabled=(not wa_ok and not dry)):
    try:
        res = enviar_recordatorios_manana(dry_run=dry)
        if res["total"] == 0:
            st.info("No hay citas para mañana.")
        else:
            st.success(f"Procesadas: {res['total']} • Enviados: {res['enviados']} • Fallidos: {res['fallidos']}")
            st.dataframe(pd.DataFrame(res["detalles"]), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"No se pudieron enviar los recordatorios: {e}")

st.divider()
if st.button("🚪 Cerrar sesión", key="btn_logout"):
    st.session_state.role = None
    st.session_state.paciente = None
    try:
        st.switch_page("pages/0_Login.py")
    except Exception:
        st.rerun()
