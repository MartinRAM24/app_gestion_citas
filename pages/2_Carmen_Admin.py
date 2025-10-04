import streamlit as st
from datetime import date, datetime
import pandas as pd
from modules.core import (
    generar_slots, crear_cita_manual, citas_por_dia,
    actualizar_cita, eliminar_cita
)

st.set_page_config(page_title="Carmen — Panel", page_icon="🗂️", layout="wide")

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

/* ===== Expanders: gris medio agradable ===== */
div[data-testid="stExpander"] > details {
  background: #2B2F36 !important;       /* panel cerrado */
  border: 1px solid #3A3F47 !important;
  border-radius: 12px !important;
}
div[data-testid="stExpander"] > details[open] {
  background: #2F343C !important;       /* panel abierto */
}
div[data-testid="stExpander"] summary {
  background: #2B2F36 !important;       /* tira del header */
  color: #EAECEF !important;
  border-radius: 12px !important;
}

/* ===== Inputs en gris (texto/number/textarea/select/date/time/multiselect) ===== */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[role="combobox"],
/* file uploader caja */
[data-testid="stFileUploader"] section[data-testid="stFileDropzone"] {
  background: #2F3136 !important;
  color: #F5F6F7 !important;
  border: 1px solid #4A4D55 !important;
  border-radius: 10px !important;
}

/* Placeholders más claros */
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
.stDataFrame div[data-testid="stTable"] {
  border-radius: 10px;
  overflow: hidden;
}

div[data-baseweb="notification"] {
  background-color: #800020 !important; 
  color: #FFFFFF !important;
}

/* Encabezados */
h1, h2, h3, h4 { color: #111827; }
"""

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

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
        elif not (nombre.strip()):
            st.error("Nombre es obligatorio.")
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

    # --------- RECORDATORIOS WHATSAPP (CITAS DE MAÑANA) ----------
    from modules.core import enviar_recordatorios_manana

    st.divider()
    st.subheader("🔔 Recordatorios de WhatsApp (citas de mañana)")

    colA, colB = st.columns([1, 3])
    with colA:
        dry = st.checkbox("Modo simulación (no envía)", value=True)

    if st.button("📨 Enviar recordatorios de mañana"):
        try:
            res = enviar_recordatorios_manana(dry_run=dry)
            if res["total"] == 0:
                st.info("No hay citas para mañana.")
            else:
                st.success(f"Procesadas: {res['total']} • Enviados: {res['enviados']} • Fallidos: {res['fallidos']}")
                st.dataframe(pd.DataFrame(res["detalles"]), use_container_width=True, hide_index=True)
        except KeyError:
            st.error("Faltan credenciales de WhatsApp en Secrets.")
        except Exception as e:
            st.error(f"No se pudieron enviar los recordatorios: {e}")

# Cerrar sesión (sustituye al antiguo st.page_link)
if st.button("🚪 Cerrar sesión"):
    st.session_state.role = None
    st.session_state.paciente = None
    st.rerun()
