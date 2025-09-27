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

@st.cache_data(show_spinner=False)
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
    df = query_df(
        "SELECT id FROM pacientes WHERE nombre = %s AND telefono = %s LIMIT 1",
        (nombre, telefono),
    )
    if not df.empty:
        return int(df.iloc[0]["id"])
    exec_sql("INSERT INTO pacientes(nombre, telefono) VALUES (%s, %s)", (nombre, telefono))
    df2 = query_df(
        "SELECT id FROM pacientes WHERE nombre = %s AND telefono = %s ORDER BY id DESC LIMIT 1",
        (nombre, telefono),
    )
    return int(df2.iloc[0]["id"])

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
ensure_schema()

st.title("🩺 Gestión de Citas — Carmen")

with st.sidebar:
    vista = st.radio("Navegación", ["📅 Agendar (Pacientes)", "🧑‍⚕️ Carmen (Admin)"])

if vista == "📅 Agendar (Pacientes)":
    st.header("📅 Agenda tu cita")

    min_day = date.today() + timedelta(days=BLOQUEO_DIAS_MIN)
    fecha = st.date_input(
        "Elige el día (disponible desde el tercer día)",
        value=min_day,
        min_value=min_day
    )

    if not is_fecha_permitida(fecha):
        st.error("Solo puedes agendar a partir del tercer día.")
        st.stop()

    ocupados = slots_ocupados(fecha)

    # Mostrar SOLO libres para evitar confusión
    libres = [t for t in generar_slots(fecha) if t not in ocupados]
    if not libres:
        st.info("No hay horarios libres en este día. Prueba con otra fecha.")
    else:
        slot_sel = st.selectbox("Horario", [t.strftime("%H:%M") for]()_

