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

/* ===== Inputs en gris ===== */
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

# ✅ NEW/CHANGED: cache simple de pacientes en sesión
if "pacientes_cache" not in st.session_state:
    st.session_state["pacientes_cache"] = []  # lista de nombres únicos

colf, colr = st.columns([1, 2], gap="large")

# ✅ NEW/CHANGED: cargamos citas del día primero para reutilizar en ambos paneles
with colf:
    fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")

# Cargar citas del día (visible para ambos contenedores)
df_dia = citas_por_dia(fecha_sel)
# Actualizar cache con nombres del día
if not df_dia.empty and "nombre" in df_dia.columns:
    nuevos = [n for n in df_dia["nombre"].dropna().astype(str).str.strip().unique() if n]
    # fusionar sin duplicar (case-insensitive por sanidad)
    cache_lower = {x.lower(): x for x in st.session_state["pacientes_cache"]}
    for n in nuevos:
        if n.lower() not in cache_lower:
            st.session_state["pacientes_cache"].append(n)

with colf:
    # Slots disponibles (de admin)
    opts_admin = [t.strftime("%H:%M") for t in generar_slots(fecha_sel)]
    slot = st.selectbox("Hora", opts_admin) if opts_admin else None
    if not opts_admin:
        st.info("Día no laborable o sin bloques disponibles.")

    # ✅ NEW/CHANGED: Selección de paciente existente O nombre nuevo
    opciones_pacientes = ["—"] + sorted(st.session_state["pacientes_cache"], key=lambda x: x.lower())
    sel_existente = st.selectbox("Paciente registrado (opcional)", opciones_pacientes, index=0, help="Puedes elegir uno ya registrado o escribir uno nuevo abajo.")
    nombre_nuevo = st.text_input("Nombre del paciente (nuevo)", placeholder="Escribe un nombre si no seleccionaste uno existente")

    # El teléfono pasa a ser OPCIONAL
    tel = st.text_input("Teléfono (opcional)", placeholder="Puedes dejarlo vacío")
    nota = st.text_area("Nota (opcional)")

    # ✅ NEW/CHANGED: Resolver nombre final (prioriza seleccionado si hay)
    nombre_final = None
    if sel_existente != "—":
        nombre_final = sel_existente
    elif nombre_nuevo.strip():
        nombre_final = nombre_nuevo.strip()

    # ✅ NEW/CHANGED: Validación de choque de horario
    # Consideramos ocupado si existe una cita con la misma hora exacta
    ocupado = False
    nombre_ocupa = None
    if slot and not df_dia.empty and "hora" in df_dia.columns:
        try:
            # df_dia["hora"] es tipo time/datetime; comparamos HH:MM
            df_dia = df_dia.copy()
            df_dia["hora_txt"] = df_dia["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)
            fila_slot = df_dia[df_dia["hora_txt"] == slot]
            if not fila_slot.empty and fila_slot["id_cita"].notna().any():
                ocupado = True
                try:
                    nombre_ocupa = fila_slot.iloc[0].get("nombre") or ""
                except Exception:
                    nombre_ocupa = ""
        except Exception:
            pass

    if st.button("➕ Crear cita"):
        if not slot:
            st.error("Selecciona un día con horarios disponibles.")
        elif not nombre_final:
            st.error("Indica el paciente: selecciona uno registrado o escribe un nombre nuevo.")
        elif ocupado:
            # ✅ NEW/CHANGED: Mensaje claro si ya hay una cita en esa hora
            detalle = f" por {nombre_ocupa}" if nombre_ocupa else ""
            st.error(f"Ya existe una cita a las {slot}{detalle}. Elige otra hora.")
        else:
            # ✅ NEW/CHANGED: teléfono opcional → pasar None si viene vacío
            try:
                crear_cita_manual(
                    fecha_sel,
                    datetime.strptime(slot, "%H:%M").time(),
                    nombre_final,
                    tel.strip() or None,
                    nota or None
                )
                # Guardamos en cache si es nuevo
                if nombre_final and nombre_final not in st.session_state["pacientes_cache"]:
                    st.session_state["pacientes_cache"].append(nombre_final)
                st.success("Cita creada.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo crear la cita: {e}")

with colr:
    st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")
    df = df_dia  # reutilizamos

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

        # ✅ NEW/CHANGED: Teléfono opcional al editar
        nombre_e = st.text_input("Nombre", (r.get("nombre") or ""), key="nombre_edit")
        tel_e    = st.text_input("Teléfono (opcional)", (r.get("telefono") or ""), key="tel_edit", placeholder="Puede quedar vacío")
        nota_e   = st.text_area("Nota", (r.get("nota") or ""), key="nota_edit")

        if st.button("💾 Guardar cambios"):
            if nombre_e.strip():
                try:
                    actualizar_cita(int(cid), nombre_e.strip(), (tel_e.strip() or None), (nota_e or None))
                    st.success("Actualizado."); st.rerun()
                except Exception as e:
                    st.error(f"No se pudo actualizar la cita: {e}")
            else:
                st.error("El nombre es obligatorio.")

        st.divider(); st.caption("Eliminar cita")
        confirm = st.checkbox("Confirmar eliminación")
        if st.button("🗑️ Eliminar", disabled=not confirm):
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

# Cerrar sesión
if st.button("🚪 Cerrar sesión"):
    st.session_state.role = None
    st.session_state.paciente = None
    st.rerun()
