import os
import psycopg
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from typing import Optional

# importa TODAS las constantes necesarias
from app_gestion_citas.constants import (
    BLOQUEO_DIAS_MIN, HORA_INICIO, HORA_FIN, PASO_MIN
)

# =====================
# Conexión a Neon / Postgres
# =====================
NEON_URL = st.secrets.get("NEON_DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

@st.cache_resource
def conn():
    if not NEON_URL:
        st.stop()  # fuerza a configurar la URL
    return psycopg.connect(NEON_URL, autocommit=True)

def exec_sql(q_ps: str, p: tuple = ()):
    """Ejecuta un SQL tipo INSERT/UPDATE/DDL"""
    with conn().cursor() as cur:
        cur.execute(q_ps, p)

@st.cache_data(show_spinner=False)
def query_df(q_ps: str, p: tuple = ()):
    """Ejecuta un SELECT y devuelve un DataFrame"""
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

# =====================
# Utilidades de agenda
# =====================
def generar_slots(fecha: date):
    """Genera horarios cada PASO_MIN entre HORA_INICIO y HORA_FIN para la fecha dada."""
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

def ensure_schema():
    with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8") as f:
        sql = f.read()
    exec_sql(sql)

# =====================
# Operaciones de negocio
# =====================
def crear_o_encontrar_paciente(nombre: str, telefono: str) -> int:
    df = query_df(
        "SELECT id FROM pacientes WHERE nombre = %s AND telefono = %s LIMIT 1",
        (nombre, telefono),
    )
    if not df.empty:
        return int(df.iloc[0]["id"])  # ya existe

    exec_sql(
        "INSERT INTO pacientes(nombre, telefono) VALUES (%s, %s)",
        (nombre, telefono),
    )
    df2 = query_df(
        "SELECT id FROM pacientes WHERE nombre = %s AND telefono = %s ORDER BY id DESC LIMIT 1",
        (nombre, telefono),
    )
    return int(df2.iloc[0]["id"])  # nuevo id

def slots_ocupados(fecha: date) -> set:
    df = query_df("SELECT hora FROM citas WHERE fecha = %s ORDER BY hora", (fecha,))
    return set(df["hora"].tolist())

def agendar_cita(fecha: date, hora: datetime.time, nombre: str, telefono: str, nota: Optional[str] = None):
    assert is_fecha_permitida(fecha), "La fecha seleccionada no está permitida (mínimo día 3)."
    pid = crear_o_encontrar_paciente(nombre.strip(), telefono.strip())
    exec_sql(
        """
        INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s, %s, %s, %s)
        """,
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
    exec_sql(
        "UPDATE citas SET paciente_id=%s, nota=%s WHERE id=%s",
        (pid, nota, cita_id),
    )

def crear_cita_manual(fecha: date, hora: datetime.time, nombre: str, telefono: str, nota: Optional[str] = None):
    # igual que agendar, pero sin la restricción de 3 días (para Carmen)
    pid = crear_o_encontrar_paciente(nombre.strip(), telefono.strip())
    exec_sql(
        "INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s, %s, %s, %s)",
        (fecha, hora, pid, nota),
    )
