# db_utils.py
import os
import psycopg
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

MX = ZoneInfo("America/Mexico_City")

def _get_neon_url():
    # Streamlit: st.secrets primero, luego env var
    try:
        import streamlit as st
        return st.secrets.get("NEON_DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    except Exception:
        return os.getenv("NEON_DATABASE_URL")

NEON_URL = _get_neon_url()

def conn():
    if not NEON_URL:
        raise RuntimeError("Configura NEON_DATABASE_URL en .streamlit/secrets.toml")
    return psycopg.connect(NEON_URL, autocommit=True)

DDL = """
CREATE TABLE IF NOT EXISTS citas (
  id BIGSERIAL PRIMARY KEY,
  paciente_nombre TEXT NOT NULL,
  paciente_telefono TEXT,
  motivo TEXT,
  profesional TEXT NOT NULL DEFAULT 'Carmen',
  fecha DATE NOT NULL,
  hora TIME NOT NULL,
  estado TEXT NOT NULL DEFAULT 'reservada', -- reservada | cancelada | atendida
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_citas_slot
ON citas (profesional, fecha, hora)
WHERE estado IN ('reservada','atendida');

-- Política de “pasado mañana” a nivel DB
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'chk_fecha_minima'
  ) THEN
    ALTER TABLE citas
      ADD CONSTRAINT chk_fecha_minima
      CHECK (fecha >= CURRENT_DATE + INTERVAL '2 days');
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS ix_citas_fecha ON citas(fecha);
CREATE INDEX IF NOT EXISTS ix_citas_prof_fecha ON citas(profesional, fecha);
"""

def ensure_schema():
    with conn().cursor() as cur:
        for stmt in [s.strip() for s in DDL.split(";\n") if s.strip()]:
            cur.execute(stmt + (";" if not stmt.endswith(";") else ""))

def slots_del_dia(fecha: date, inicio: time = time(9,0),
                  fin: time = time(19,0), paso_min: int = 30):
    dt = datetime.combine(fecha, inicio)
    end = datetime.combine(fecha, fin)
    res = []
    while dt <= end - timedelta(minutes=paso_min):
        res.append(dt.time().replace(second=0, microsecond=0))
        dt += timedelta(minutes=paso_min)
    return res

def slots_ocupados(fecha: date, profesional: str = "Carmen"):
    q = """
    SELECT hora FROM citas
    WHERE profesional=%s AND fecha=%s AND estado IN ('reservada','atendida')
    ORDER BY hora;
    """
    with conn().cursor() as cur:
        cur.execute(q, (profesional, fecha))
        return {r[0] for r in cur.fetchall()}

def crear_cita(paciente_nombre: str, paciente_telefono: str, motivo: str,
               fecha: date, hora: time, profesional: str = "Carmen"):
    q = """
    INSERT INTO citas (paciente_nombre, paciente_telefono, motivo, profesional, fecha, hora)
    VALUES (%s,%s,%s,%s,%s,%s)
    RETURNING id;
    """
    with conn().cursor() as cur:
        cur.execute(q, (paciente_nombre, paciente_telefono, motivo, profesional, fecha, hora))
        return cur.fetchone()[0]

def listar_citas(fecha: date = None, profesional: str = None, estado: str = None):
    base = """
    SELECT id, paciente_nombre, paciente_telefono, motivo,
           profesional, fecha, hora, estado, created_at
    FROM citas WHERE 1=1
    """
    params = []
    if fecha:
        base += " AND fecha=%s"
        params.append(fecha)
    if profesional:
        base += " AND profesional=%s"
        params.append(profesional)
    if estado:
        base += " AND estado=%s"
        params.append(estado)
    base += " ORDER BY fecha, hora"
    with conn().cursor() as cur:
        cur.execute(base, tuple(params))
        return cur.fetchall()

def cambiar_estado_cita(cita_id: int, nuevo_estado: str):
    q = "UPDATE citas SET estado=%s WHERE id=%s"
    with conn().cursor() as cur:
        cur.execute(q, (nuevo_estado, cita_id))
