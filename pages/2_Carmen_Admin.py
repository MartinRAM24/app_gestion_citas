from datetime import date, datetime
import pandas as pd
from modules.core import (
    generar_slots, crear_cita_manual, citas_por_dia,
    actualizar_cita, eliminar_cita,
    listar_pacientes, crear_cita_para_paciente
)
import base64, hmac, hashlib, json, time
import os, streamlit as st

def read_secret(name: str, default: str | None = None) -> str | None:
    # 1) Railway / entorno: variable de entorno
    val = os.getenv(name)
    if val:
        return val
    # 2) Opcional: secrets.toml (solo si existe)
    try:
        return st.secrets[name]
    except Exception:
        return default

SECRET = read_secret("APP_AUTH_SECRET", "dev-secret-please-set")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def verify_token(token: str):
    try:
        body_b64, sig_b64 = token.split(".")
        body = _b64u_decode(body_b64)
        sig = _b64u_decode(sig_b64)
        calc = hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, calc):
            return None
        data = json.loads(body.decode())
        if int(time.time()) > int(data.get("exp", 0)):
            return None
        return data
    except Exception:
        return None

def get_url_token() -> str | None:
    return st.query_params.get("s")

# --- Guard: solo admin con token válido ---
data = verify_token(get_url_token() or "")
if not data or data.get("role") != "admin":
    st.switch_page("pages/0_Login.py")

st.session_state.role = "admin"
st.session_state.paciente = None


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

/* ===== Expanders ===== */
div[data-testid="stExpander"] > details {
  background: #2B2F36 !important;
  border: 1px solid #3A3F47 !important;
  border-radius: 12px !important;
}
div[data-testid="stExpander"] > details[open] {
  background: #2F343C !important;
}
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

# 1) Día seleccionado y citas del día (disponibles para ambos paneles)
fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")
df_dia = citas_por_dia(fecha_sel)  # una sola vez

# 2) Utilidad: strip seguro (evita NoneType.strip)
def _s(x):
    return (x or "").strip()

# 3) Columnas
colf, colr = st.columns([1, 2], gap="large")

with colf:
    # Horas del día
    opts_admin = [t.strftime("%H:%M") for t in generar_slots(fecha_sel)]
    slot = st.selectbox("Hora", opts_admin, key="hora_admin") if opts_admin else None
    if not opts_admin:
        st.info("Día no laborable o sin bloques disponibles.")

    # ── Paciente: un solo control con buscador integrado ──
    df_pac = listar_pacientes(None)  # trae solo con teléfono

    # IDs como value reales; 0 = NUEVO
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
        help="Escribe parte del nombre o teléfono para filtrar. Si lo dejas en la primera opción, crea uno nuevo abajo."
    )
    sel_id = None if sel_val == 0 else sel_val

    # Prefill si seleccionaste un paciente
    nombre_def, tel_def = "", ""
    if sel_id is not None and not df_pac.empty:
        r0 = df_pac.loc[df_pac["id"] == sel_id]
        if not r0.empty:
            r0 = r0.iloc[0]
            nombre_def = r0.get("nombre") or ""
            tel_def    = r0.get("telefono") or ""

    # Campos SIEMPRE visibles (nuevo o seleccionado)
    nombre_nuevo = st.text_input(
        "Nombre del paciente (si es nuevo)",
        value=nombre_def,
        placeholder="Escribe el nombre SOLO si no seleccionaste uno registrado",
        key="nombre_nuevo"
    )
    tel = st.text_input("Teléfono (opcional)", value=tel_def, placeholder="Puedes dejarlo vacío", key="tel_nuevo")
    nota = st.text_area("Nota (opcional)", key="nota_nueva")

    # Choque de horario (misma hora ocupada)
    ocupado, nombre_ocupa = False, None
    if slot and not df_dia.empty and "hora" in df_dia.columns:
        df_tmp = df_dia.copy()
        df_tmp["hora_txt"] = df_tmp["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)
        fila_slot = df_tmp[df_tmp["hora_txt"] == slot]
        if not fila_slot.empty and fila_slot["id_cita"].notna().any():
            ocupado = True
            try:
                nombre_ocupa = fila_slot.iloc[0].get("nombre")
            except Exception:
                nombre_ocupa = None

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
                    # Paciente registrado (ID real)
                    crear_cita_para_paciente(fecha_sel, h, sel_id, _s(nota) or None)
                else:
                    # Nuevo paciente (tel opcional)
                    if not _s(nombre_nuevo):
                        st.error("Escribe el nombre del paciente (o selecciona uno registrado arriba).")
                        st.stop()
                    crear_cita_manual(
                        fecha_sel,
                        h,
                        _s(nombre_nuevo),
                        _s(tel),              # "" si vacío
                        _s(nota) or None      # NULL si vacío
                    )
                st.success("Cita creada.")
                st.rerun()
            except Exception as e:
                err = str(e)
                if "uniq_fecha_hora" in err or "UniqueViolation" in err:
                    st.error(f"Esa hora ya está ocupada ({slot}). Elige otra.")
                else:
                    st.error(f"No se pudo crear la cita: {e}")

with colr:
    st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")
    df = df_dia

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
            if c not in show.columns:
                show[c] = None
        st.dataframe(show[cols], use_container_width=True)
    else:
        st.info("Domingo (no laborable).")

    if df.empty:
        st.info("No hay citas ocupadas en este día.")
    else:
        st.divider(); st.caption("Editar / eliminar cita")
        ids = df["id_cita"].astype(int).tolist()
        cid = st.selectbox("ID cita", ids, key="cid_edit")
        r = df[df.id_cita == cid].iloc[0]

        nombre_e = st.text_input("Nombre", (r.get("nombre") or ""), key="nombre_edit")
        tel_e    = st.text_input("Teléfono (opcional)", (r.get("telefono") or ""), key="tel_edit", placeholder="Puede quedar vacío")
        nota_e   = st.text_area("Nota", (r.get("nota") or ""), key="nota_edit")

        if st.button("💾 Guardar cambios", key="btn_guardar"):
            if _s(nombre_e):
                try:
                    actualizar_cita(int(cid), _s(nombre_e), (_s(tel_e) or None), (_s(nota_e) or None))
                    st.success("Actualizado."); st.rerun()
                except Exception as e:
                    st.error(f"No se pudo actualizar la cita: {e}")
            else:
                st.error("El nombre es obligatorio.")

        st.divider(); st.caption("Eliminar cita")
        confirm = st.checkbox("Confirmar eliminación", key="chk_del")
        if st.button("🗑️ Eliminar", disabled=not confirm, key="btn_del"):
            try:
                n = eliminar_cita(int(cid))
                st.success("Cita eliminada." if n else "La cita ya no existía.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar la cita: {e}")

# --------- RECORDATORIOS WHATSAPP (CITAS DE MAÑANA) ----------
from modules.core import enviar_recordatorios_manana

st.divider()
st.subheader("🔔 Recordatorios de WhatsApp (citas de mañana)")

colA, colB = st.columns([1, 3])
with colA:
    dry = st.checkbox("Modo simulación (no envía)", value=True, key="dry_wa")

if st.button("📨 Enviar recordatorios de mañana", key="btn_wa"):
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

if st.button("🚪 Cerrar sesión", key="btn_logout"):
    st.query_params.clear()  # limpia ?s=
    st.session_state.role = None
    st.session_state.paciente = None
    st.rerun()


