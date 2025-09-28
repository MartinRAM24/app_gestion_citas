import streamlit as st
from datetime import date, datetime, timedelta
from modules.core import (
    generar_slots, slots_ocupados, agendar_cita_autenticado,
    proxima_cita_paciente, is_fecha_permitida, BLOQUEO_DIAS_MIN
)

st.set_page_config(page_title="Paciente — Agenda", page_icon="📅", layout="wide")

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
