# modules/core.py — DB + lógica común
import os, re, bcrypt
from typing import Optional
from datetime import date, datetime, timedelta, time
import pandas as pd
import psycopg
from psycopg import errors as pg_errors
import streamlit as st
import requests

# --- helpers seguros para secrets ---
def _sget(key: str, default=None):
    try:
        # Streamlit: si existe secrets.toml lo usa; si no, lanza excepción
        return st.secrets.get(key, default)
    except Exception:
        return default

def _sget_block(block: str) -> dict:
    try:
        return dict(st.secrets.get(block, {}))
    except Exception:
        return {}

# ---------- Config ----------
HORA_INICIO: time = time(9, 0)
HORA_FIN:    time = time(17, 0)
PASO_MIN:    int  = 30
BLOQUEO_DIAS_MIN: int = 2

# Prioriza ENV (Railway) y luego secrets (Streamlit)
NEON_URL = os.getenv("NEON_DATABASE_URL") or _sget("NEON_DATABASE_URL")

ADMIN_USER = (
    os.getenv("ADMIN_USER")
    or os.getenv("CARMEN_USER")
    or _sget("ADMIN_USER")
    or _sget("CARMEN_USER", "carmen")
)
ADMIN_PASSWORD = (
    os.getenv("ADMIN_PASSWORD")
    or os.getenv("CARMEN_PASSWORD")
    or _sget("ADMIN_PASSWORD")
    or _sget("CARMEN_PASSWORD")
)

PEPPER = (os.getenv("PASSWORD_PEPPER") or _sget("PASSWORD_PEPPER", "") or "").encode()

def normalize_tel(t: str) -> str:
    return re.sub(r'[-\s]+', '', t.strip().lower())

def _peppered(pw: str) -> bytes:
    return (pw.encode() + PEPPER) if PEPPER else pw.encode()

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(_peppered(pw), bcrypt.gensalt()).decode()

def check_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_peppered(pw), pw_hash.encode())
    except Exception:
        return False

def is_admin_ok(user: str, pw: str) -> bool:
    return bool(ADMIN_USER and ADMIN_PASSWORD and user == ADMIN_USER and pw == ADMIN_PASSWORD)

# ---------- Conexión ----------
@st.cache_resource
def _connect():
    if not NEON_URL:
        st.error("Falta configurar NEON_DATABASE_URL (ENV o Secrets).")
        st.stop()
    return psycopg.connect(NEON_URL, autocommit=True)

def conn():
    c = _connect()
    try:
        if getattr(c, "closed", False):
            raise psycopg.OperationalError("closed")
        with c.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        c = _connect()
    return c

def exec_sql(q_ps: str, p: tuple = ()):
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
    try:
        st.cache_data.clear()
    except Exception:
        pass

@st.cache_data(show_spinner=False, ttl=5)
def query_df(q_ps: str, p: tuple = ()):
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

def query_df_fresh(q_ps: str, p: tuple = ()):
    with conn().cursor() as cur:
        cur.execute(q_ps, p)
        cols = [c.name for c in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

# ---------- Esquema ----------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pacientes (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL,
  telefono TEXT NOT NULL UNIQUE,
  password_hash TEXT,
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

# Ejecuta al importar
ensure_schema()

# ---------- Lógica agenda ----------
def _fmt_fecha(v) -> str:
    try: return pd.to_datetime(v).strftime("%d-%m-%Y")
    except Exception: return str(v)

def _fmt_hora(v) -> str:
    try: return pd.to_datetime(str(v)).strftime("%H:%M")
    except Exception: return str(v)

def proxima_cita_paciente(paciente_id: int):
    return query_df(
        """
        SELECT c.id AS id_cita, c.fecha, c.hora, c.nota
        FROM citas c
        WHERE c.paciente_id = %s
          AND (c.fecha > CURRENT_DATE OR (c.fecha = CURRENT_DATE AND c.hora >= CURRENT_TIME))
        ORDER BY c.fecha, c.hora
        LIMIT 1
        """,
        (paciente_id,),
    )

def registrar_paciente(nombre: str, telefono: str, password: str) -> int:
    tel = normalize_tel(telefono)
    pw_hash = hash_password(password)
    with conn().cursor() as cur:
        cur.execute(
            "INSERT INTO pacientes (nombre, telefono, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (nombre.strip(), tel, pw_hash),
        )
        pid = cur.fetchone()[0]
    try: st.cache_data.clear()
    except Exception: pass
    return int(pid)

def login_paciente(telefono: str, password: str) -> Optional[dict]:
    tel = normalize_tel(telefono)
    df = query_df(
        "SELECT id, nombre, telefono, password_hash FROM pacientes WHERE telefono = %s LIMIT 1",
        (tel,),
    )
    if df.empty:
        return None
    row = df.iloc[0]
    if row.get("password_hash") and check_password(password, str(row["password_hash"])):
        return {"id": int(row["id"]), "nombre": row["nombre"], "telefono": row["telefono"]}
    return None

def ya_tiene_cita_en_dia(paciente_id: int, fecha: date) -> bool:
    df = query_df_fresh("SELECT 1 FROM citas WHERE paciente_id=%s AND fecha=%s LIMIT 1", (paciente_id, fecha))
    return not df.empty

def ya_tiene_cita_en_ventana_7dias(paciente_id: int, fecha_ref: date) -> bool:
    df = query_df_fresh(
        """
        SELECT 1 FROM citas
        WHERE paciente_id=%s
          AND fecha BETWEEN (%s::date - INTERVAL '6 days') AND (%s::date + INTERVAL '6 days')
        LIMIT 1
        """,
        (paciente_id, fecha_ref, fecha_ref),
    )
    return not df.empty

def is_fecha_permitida(fecha: date) -> bool:
    return fecha >= (date.today() + timedelta(days=BLOQUEO_DIAS_MIN))

def _bloques_del_dia(fecha: date) -> list[tuple[time, time]]:
    wd = fecha.weekday()
    if 0 <= wd <= 4:
        return [(time(10,0), time(12,0)), (time(14,0), time(16,30)), (time(18,30), time(19,0))]
    elif wd == 5:
        return [(time(8,0), time(14,0))]
    else:
        return []

def generar_slots(fecha: date) -> list[time]:
    slots, delta = [], timedelta(minutes=PASO_MIN)
    for ini, fin in _bloques_del_dia(fecha):
        t = datetime.combine(fecha, ini); tfin = datetime.combine(fecha, fin)
        while t < tfin:
            slots.append(t.time()); t += delta
    return slots

def slots_ocupados(fecha: date) -> set:
    df = query_df("SELECT hora FROM citas WHERE fecha=%s ORDER BY hora", (fecha,))
    return set(df["hora"].tolist())

def agendar_cita_autenticado(fecha: date, hora: time, paciente_id: int, nota: Optional[str] = None):
    assert is_fecha_permitida(fecha), "La fecha seleccionada no está permitida (mínimo día 3)."
    if ya_tiene_cita_en_dia(paciente_id, fecha):
        raise ValueError("Ya tienes una cita ese día. Solo se permite una por día.")
    if ya_tiene_cita_en_ventana_7dias(paciente_id, fecha):
        raise ValueError("Solo se permite una cita cada 7 días (respecto a la fecha elegida).")
    try:
        exec_sql("INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s,%s,%s,%s)",
                 (fecha, hora, paciente_id, nota))
    except pg_errors.UniqueViolation:
        raise ValueError("Ese horario ya fue tomado. Elige otro.")

def crear_o_encontrar_paciente(nombre: str, telefono: str) -> int:
    tel = normalize_tel(telefono)
    df = query_df("SELECT id FROM pacientes WHERE telefono=%s LIMIT 1", (tel,))
    if not df.empty:
        return int(df.iloc[0]["id"])
    with conn().cursor() as cur:
        cur.execute("INSERT INTO pacientes(nombre, telefono) VALUES (%s,%s) RETURNING id", (nombre.strip(), tel))
        new_id = cur.fetchone()[0]
    try: st.cache_data.clear()
    except Exception: pass
    return int(new_id)

def crear_cita_manual(fecha: date, hora: time, nombre: str, telefono: str, nota: Optional[str] = None):
    pid = crear_o_encontrar_paciente(nombre, telefono)
    exec_sql("INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s,%s,%s,%s)",
             (fecha, hora, pid, nota))

def citas_por_dia(fecha: date):
    return query_df(
        """
        SELECT c.id AS id_cita, c.fecha, c.hora, p.id AS paciente_id, p.nombre, p.telefono, c.nota
        FROM citas c LEFT JOIN pacientes p ON p.id=c.paciente_id
        WHERE c.fecha=%s ORDER BY c.hora
        """,
        (fecha,),
    )

def actualizar_cita(cita_id: int, nombre: str, telefono: str, nota: Optional[str]):
    pid = crear_o_encontrar_paciente(nombre, telefono)
    exec_sql("UPDATE citas SET paciente_id=%s, nota=%s WHERE id=%s", (pid, nota, cita_id))

def eliminar_cita(cita_id: int) -> int:
    with conn().cursor() as cur:
        cur.execute("DELETE FROM citas WHERE id=%s", (cita_id,))
        n = cur.rowcount or 0
    try: st.cache_data.clear()
    except Exception: pass
    return n

# ========== WHATSAPP / RECORDATORIOS ==========

def _get_whatsapp_cfg() -> dict:
    """
    1) ENV (Railway): WHATSAPP_TOKEN / _PHONE_NUMBER_ID / _TEMPLATE / _LANG
    2) secrets.toml (Streamlit): [whatsapp] TOKEN / PHONE_NUMBER_ID / TEMPLATE / LANG
    """
    env_cfg = {
        "TOKEN": os.getenv("WHATSAPP_TOKEN"),
        "PHONE_NUMBER_ID": os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
        "TEMPLATE": os.getenv("WHATSAPP_TEMPLATE"),
        "LANG": os.getenv("WHATSAPP_LANG"),
    }
    # Si en ENV ya está completo, úsalo
    if env_cfg["TOKEN"] and env_cfg["PHONE_NUMBER_ID"] and env_cfg["TEMPLATE"]:
        env_cfg["LANG"] = env_cfg["LANG"] or "es_MX"
        return env_cfg

    # Si no, intenta secrets.toml
    sec = _sget_block("whatsapp")
    return {
        "TOKEN": sec.get("TOKEN"),
        "PHONE_NUMBER_ID": sec.get("PHONE_NUMBER_ID"),
        "TEMPLATE": sec.get("TEMPLATE"),
        "LANG": sec.get("LANG", "es_MX"),
    }

def _wa_send_meta(to_e164: str, nombre: str, fecha_txt: str, hora_txt: str):
    cfg = _get_whatsapp_cfg()
    missing = [k for k in ("TOKEN", "PHONE_NUMBER_ID", "TEMPLATE") if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"Config WhatsApp incompleta (falta: {', '.join(missing)}).")

    url = f"https://graph.facebook.com/v19.0/{cfg['PHONE_NUMBER_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {cfg['TOKEN']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_e164,
        "type": "template",
        "template": {
            "name": cfg["TEMPLATE"],
            "language": {"code": cfg.get("LANG", "es_MX")},
            "components": [
                {"type": "body", "parameters": [
                    {"type": "text", "text": nombre or "Paciente"},
                    {"type": "text", "text": fecha_txt},
                    {"type": "text", "text": hora_txt},
                ]}
            ],
        },
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def _fmt_fecha_es(v) -> str:
    try: return pd.to_datetime(v).strftime("%d/%m/%Y")
    except Exception: return str(v)

def _fmt_hora_es(v) -> str:
    try: return pd.to_datetime(str(v)).strftime("%H:%M")
    except Exception: return str(v)

def _to_e164_mx(tel: str) -> str | None:
    """Normaliza teléfonos a E.164 (+52XXXXXXXXXX si recibe 10 dígitos de MX)."""
    if not tel: return None
    t = re.sub(r"\D+", "", str(tel))
    if not t: return None
    if str(tel).startswith("+"):
        return str(tel)
    if t.startswith("52"):
        return f"+{t}"
    if len(t) == 10:
        return f"+52{t}"
    return None

def citas_manana():
    """Citas de mañana (fecha = hoy + 1) con datos de paciente."""
    return query_df(
        """
        SELECT c.id AS id_cita, c.fecha, c.hora, c.nota,
               p.id AS paciente_id, p.nombre, p.telefono
        FROM citas c
        JOIN pacientes p ON p.id = c.paciente_id
        WHERE c.fecha = CURRENT_DATE + INTERVAL '1 day'
        ORDER BY c.hora
        """
    )

def enviar_recordatorios_manana(dry_run: bool = False) -> dict:
    """
    Envía (o simula) recordatorios de WhatsApp para TODAS las citas de mañana.
    Devuelve resumen {"total", "enviados", "fallidos", "detalles":[...]}.
    """
    df = citas_manana()
    res = {"total": int(len(df)), "enviados": 0, "fallidos": 0, "detalles": []}
    if df.empty:
        return res

    for _, r in df.iterrows():
        nombre = (r.get("nombre") or "").strip()
        tel_raw = (r.get("telefono") or "").strip()
        to = _to_e164_mx(tel_raw)
        fecha_txt = _fmt_fecha_es(r["fecha"])
        hora_txt  = _fmt_hora_es(r["hora"])

        item = {
            "id_cita": int(r["id_cita"]),
            "nombre": nombre,
            "telefono": tel_raw,
            "to_e164": to or "",
            "fecha": fecha_txt,
            "hora": hora_txt,
            "ok": False,
            "error": "",
        }

        if not to:
            item["error"] = "Teléfono inválido/no E.164"
            res["fallidos"] += 1
            res["detalles"].append(item)
            continue

        try:
            if not dry_run:
                _wa_send_meta(to, nombre, fecha_txt, hora_txt)
            item["ok"] = True
            res["enviados"] += 1
        except Exception as e:
            item["error"] = str(e)
            res["fallidos"] += 1

        res["detalles"].append(item)

    return res

