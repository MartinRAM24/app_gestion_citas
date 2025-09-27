# app.py — Gestión de Citas (1 archivo, menú lateral)
import os
from typing import Optional
from datetime import date, datetime, timedelta, time

import pandas as pd
import psycopg
import streamlit as st

# =========================
# Configuración base
# =========================
st.set_page_config(page_title="Gestión de Citas - Carmen", page_icon="🩺", layout="wide")

# Ajustes de agenda
HORA_INICIO: time = time(9, 0)     # 09:00
HORA_FIN:    time = time(17, 0)    # 17:00
PASO_MIN:    int  = 30             # minutos
BLOQUEO_DIAS_MIN: int = 2          # hoy y mañana bloqueados; pacientes agendan desde el día 3

# =========================
# Conexión a Neon / Postgres
# =========================
NEON_URL = st.secrets.get("NEON_DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

@st.cache_resource
def conn():
    if not NEON_URL:
        st.error("Falta configurar NEON_DATABASE_URL en Secrets.")
        st.stop()
    return psycopg.connect(NEON_URL, autocommit=True)

def exec_sql(q_ps: str, p: tuple = ()):
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
    # Limpia caché de SELECTs para ver cambios al instante
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False, ttl=5)  # TTL para evitar resultados viejos
def query_df(q_ps: str, p: tuple = ()):
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

# =========================
# Esquema (se crea si no existe)
# =========================
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pacientes (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL,
  telefono TEXT NOT NULL,
  creado_en TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS citas (
  id SERIAL PRIMARY KEY,
  fecha DATE NOT NULL,
  hora TIME NOT NULL,
  paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
  nota TEXT,
  creado_en TIMESTAMP DEFAULT now(),
  UNIQUE (fecha, hora)
);

CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas(fecha);
"""

def ensure_schema():
    exec_sql(SCHEMA_SQL)

# =========================
# Lógica de agenda
# =========================
def generar_slots(fecha: date):
    """Genera horarios cada PASO_MIN entre HORA_INICIO y HORA_FIN."""
    slots = []
    t = datetime.combine(fecha, HORA_INICIO)
    fin = datetime.combine(fecha, HORA_FIN)
    delta = timedelta(minutes=PASO_MIN)
    while t <= fin:
        slots.append(t.time())
        t += delta
    return slots

def is_fecha_permitida(fecha: date) -> bool:
    hoy = date.today()
    return fecha >= (hoy + timedelta(days=BLOQUEO_DIAS_MIN))

def crear_o_encontrar_paciente(nombre: str, telefono: str) -> int:
    # ¿ya existe?
    df = query_df(
        "SELECT id FROM pacientes WHERE nombre = %s AND telefono = %s LIMIT 1",
        (nombre, telefono),
    )
    if not df.empty:
        return int(df.iloc[0]["id"])
    # crear y devolver id de forma segura
    with conn().cursor() as cur:
        cur.execute(
            "INSERT INTO pacientes(nombre, telefono) VALUES (%s, %s) RETURNING id",
            (nombre, telefono),
        )
        new_id = cur.fetchone()[0]
    try:
        st.cache_data.clear()
    except Exception:
        pass
    return int(new_id)

def slots_ocupados(fecha: date) -> set:
    df = query_df("SELECT hora FROM citas WHERE fecha = %s ORDER BY hora", (fecha,))
    return set(df["hora"].tolist())

def agendar_cita(fecha: date, hora: time, nombre: str, telefono: str, nota: Optional[str] = None):
    assert is_fecha_permitida(fecha), "La fecha seleccionada no está permitida (mínimo día 3)."
    pid = crear_o_encontrar_paciente(nombre.strip(), telefono.strip())
    exec_sql(
        "INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s, %s, %s, %s)",
        (fecha, hora, pid, nota),
    )

def citas_por_dia(fecha: date):
    return query_df(
        """
        SELECT c.id, c.fecha, c.hora, p.nombre, p.telefono, c.nota
        FROM citas c
        LEFT JOIN pacientes p ON p.id = c.paciente_id
        WHERE c.fecha = %s
        ORDER BY c.hora
        """,
        (fecha,),
    )

def actualizar_cita(cita_id: int, nombre: str, telefono: str, nota: Optional[str]):
    pid = crear_o_encontrar_paciente(nombre.strip(), telefono.strip())
    exec_sql("UPDATE citas SET paciente_id=%s, nota=%s WHERE id=%s", (pid, nota, cita_id))

def crear_cita_manual(fecha: date, hora: time, nombre: str, telefono: str, nota: Optional[str] = None):
    pid = crear_o_encontrar_paciente(nombre.strip(), telefono.strip())
    exec_sql(
        "INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s, %s, %s, %s)",
        (fecha, hora, pid, nota),
    )

# =========================
# UI
# =========================
#ensure_schema()

st.title("🩺 Gestión de Citas — Carmen")

with st.sidebar:
    vista = st.radio("Navegación", ["📅 Agendar (Pacientes)", "🧑‍⚕️ Carmen (Admin)"])

# ====== Vista: Pacientes ======
if vista == "📅 Agendar (Pacientes)":

    st.header("📅 Agenda tu cita")

    min_day = date.today() + timedelta(days=BLOQUEO_DIAS_MIN)
    fecha = st.date_input(
        "Elige el día (disponible desde el tercer día)",
        value=min_day,
        min_value=min_day
    )

    # Validación de fecha
    if not is_fecha_permitida(fecha):
        st.error("Solo puedes agendar a partir del tercer día.")
        st.stop()

    # Carga de horarios
    ocupados = slots_ocupados(fecha)
    libres = [t for t in generar_slots(fecha) if t not in ocupados]

    # Selector de horario (si no hay, mostramos un placeholder)
    if libres:
        opciones_horas = [t.strftime("%H:%M") for t in libres]
        slot_sel = st.selectbox("Horario disponible", opciones_horas)
    else:
        slot_sel = None
        st.warning("No hay horarios libres en este día. Prueba con otra fecha.")

    # Campos SIEMPRE visibles
    nombre = st.text_input("Tu nombre")
    telefono = st.text_input("Tu teléfono")
    nota = st.text_area("Motivo o nota (opcional)")

    # Botón (deshabilitado si no hay horarios)
    confirmar = st.button("📝 Confirmar cita", disabled=(slot_sel is None))

    if confirmar:
        if not (nombre.strip() and telefono.strip()):
            st.error("Nombre y teléfono son obligatorios.")
        elif slot_sel is None:
            st.error("No hay un horario disponible seleccionado.")
        else:
            try:
                hora = datetime.strptime(slot_sel, "%H:%M").time()
                agendar_cita(fecha, hora, nombre, telefono, nota or None)
                st.success("¡Cita agendada! Te esperamos ✨")
                st.balloons()
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo agendar: {e}")

# ====== Vista: Carmen (Admin) ======
else:
    st.header("🧑‍⚕️ Panel de Carmen")

    colf, colr = st.columns([1, 2], gap="large")

    with colf:
        fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")
        st.caption("Puedes crear citas manualmente (sin restricción de 3 días).")

        slot = st.selectbox("Hora", [t.strftime("%H:%M") for t in generar_slots(fecha_sel)], key="hora_admin")
        nombre = st.text_input("Nombre paciente", key="nombre_admin")
        tel = st.text_input("Teléfono", key="tel_admin")
        nota = st.text_area("Nota (opcional)", key="nota_admin")

        if st.button("➕ Crear cita", key="crear_admin"):
            if nombre.strip() and tel.strip():
                try:
                    crear_cita_manual(
                        fecha_sel,
                        datetime.strptime(slot, "%H:%M").time(),
                        nombre,
                        tel,
                        nota or None
                    )
                    st.success("Cita creada.")
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo crear la cita: {e}")
            else:
                st.error("Nombre y teléfono son obligatorios.")

    with colr:
        st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")

        if st.button("🔄 Actualizar lista", key="refresh_admin"):
            try:
                st.cache_data.clear()
            except Exception:
                pass
            st.rerun()

        df = citas_por_dia(fecha_sel)
        if df.empty:
            st.info("No hay citas aún.")
        else:
            st.dataframe(df, use_container_width=True)
            st.divider()
            st.caption("Editar cita")

            ids = df["id"].astype(int).tolist()
            cid = st.selectbox("ID cita", ids, key="cid_admin")
            r = df[df.id == cid].iloc[0]

            nombre_e = st.text_input("Nombre", r["nombre"] or "", key="nombre_edit")
            tel_e    = st.text_input("Teléfono", r["telefono"] or "", key="tel_edit")
            nota_e   = st.text_area("Nota", r["nota"] or "", key="nota_edit")

            if st.button("💾 Guardar cambios", key="save_edit"):
                if nombre_e.strip() and tel_e.strip():
                    try:
                        actualizar_cita(int(cid), nombre_e, tel_e, nota_e or None)
                        st.success("Actualizado.")
                        try:
                            st.cache_data.clear()
                        except Exception:
                            pass
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo actualizar: {e}")
                else:
                    st.error("Nombre y teléfono son obligatorios.")


