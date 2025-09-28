# app.py — Gestión de Citas (1 archivo, menú lateral)
import os
from typing import Optional
from datetime import date, datetime, timedelta, time
import pandas as pd
import psycopg
import streamlit as st
import re
import bcrypt
from psycopg import errors as pg_errors  # para capturar UniqueViolation, etc.

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


# (opcional) pepper para el hash; añade PASSWORD_PEPPER en Secrets si quieres
PEPPER = (st.secrets.get("PASSWORD_PEPPER") or os.getenv("PASSWORD_PEPPER") or "").encode()

def normalize_tel(t: str) -> str:
    # quita espacios y guiones; usaremos el normalizado como teléfono
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


# --- Auth de admin (Carmen) ---
ADMIN_USER = os.getenv("ADMIN_USER") or st.secrets.get("CARMEN_USER", "carmen")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or st.secrets.get("CARMEN_PASSWORD")

def require_admin_auth() -> bool:
    """Muestra formulario de login para Carmen y guarda sesión en st.session_state."""
    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

    # Si ya está logueada, muestra estado y botón de salir
    if st.session_state.admin_authed:
        with st.sidebar:
            st.success(f"Sesión: {st.session_state.get('admin_user','Carmen')}")
            if st.button("Cerrar sesión"):
                st.session_state.admin_authed = False
                st.session_state.admin_user = None
                st.rerun()
        return True

    # Formulario de login
    st.subheader("🔐 Acceso restringido")
    with st.form("login_admin"):
        u = st.text_input("Usuario", key="admin_user_input")
        p = st.text_input("Contraseña", type="password", key="admin_pass_input")
        ok = st.form_submit_button("Entrar")

    if ok:
        if not ADMIN_USER or not ADMIN_PASSWORD:
            st.error("Falta configurar CARMEN_USER y CARMEN_PASSWORD en Secrets.")
            return False
        if u == ADMIN_USER and p == ADMIN_PASSWORD:
            st.session_state.admin_authed = True
            st.session_state.admin_user = u
            st.success("Bienvenida, Carmen.")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    else:
        st.info("Ingresa tus credenciales para acceder al panel.")

    return False

@st.cache_resource
def _connect():
    if not NEON_URL:
        st.error("Falta configurar NEON_DATABASE_URL en Secrets.")
        st.stop()
    return psycopg.connect(NEON_URL, autocommit=True)

def conn():
    """Devuelve una conexión viva; si está cerrada o murió, se reconecta."""
    c = _connect()
    try:
        if getattr(c, "closed", False):
            raise psycopg.OperationalError("closed")
        # ping barato
        with c.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        # resetea el recurso y vuelve a conectar
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        c = _connect()
    return c


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
# --- Próxima cita: helpers y consulta ---
def _fmt_fecha(v) -> str:
    try:
        return pd.to_datetime(v).strftime('%d-%m-%Y')
    except Exception:
        return str(v)

def _fmt_hora(v) -> str:
    try:
        return pd.to_datetime(str(v)).strftime('%H:%M')
    except Exception:
        return str(v)

def proxima_cita_paciente(paciente_id: int):
    """Devuelve un DataFrame con la próxima cita (>= ahora) del paciente."""
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

def _get_paciente() -> dict | None:
    p = st.session_state.get("patient")
    if isinstance(p, dict) and "id" in p:
        return p
    return None

def registrar_paciente(nombre: str, telefono: str, password: str) -> int:
    tel = normalize_tel(telefono)
    pw_hash = hash_password(password)
    with conn().cursor() as cur:
        cur.execute(
            "INSERT INTO pacientes (nombre, telefono, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (nombre.strip(), tel, pw_hash),
        )
        pid = cur.fetchone()[0]
    try:
        st.cache_data.clear()
    except Exception:
        pass
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
    pw_hash = row.get("password_hash")
    if pw_hash and check_password(password, str(pw_hash)):
        return {"id": int(row["id"]), "nombre": row["nombre"], "telefono": row["telefono"]}
    return None

def ya_tiene_cita_en_dia(paciente_id: int, fecha: date) -> bool:
    df = query_df("SELECT 1 FROM citas WHERE paciente_id = %s AND fecha = %s LIMIT 1", (paciente_id, fecha))
    return not df.empty

def agendar_cita_autenticado(fecha: date, hora: time, paciente_id: int, nota: Optional[str] = None):
    assert is_fecha_permitida(fecha), "La fecha seleccionada no está permitida (mínimo día 3)."
    if ya_tiene_cita_en_dia(paciente_id, fecha):
        raise ValueError("Ya tienes una cita ese día. Solo se permite una por día.")
    try:
        exec_sql(
            "INSERT INTO citas(fecha, hora, paciente_id, nota) VALUES (%s, %s, %s, %s)",
            (fecha, hora, paciente_id, nota),
        )
    except pg_errors.UniqueViolation:
        # por si lo bloquea el constraint de BD
        raise ValueError("Ya tienes una cita ese día. Solo se permite una por día.")

# ── Horarios por día ─────────────────────────────────────────────
# Lunes-Viernes: 10:00–12:00, 14:00–16:30, 18:30–19:00
# Sábado:        08:00–14:00
# Domingo:       sin atención (sin slots)

def _bloques_del_dia(fecha: date) -> list[tuple[time, time]]:
    wd = fecha.weekday()  # 0=lun ... 6=dom
    if 0 <= wd <= 4:
        return [
            (time(10, 0), time(12, 0)),
            (time(14, 0), time(16, 30)),
            (time(18, 30), time(19, 0)),
        ]
    elif wd == 5:  # sábado
        return [(time(8, 0), time(14, 0))]
    else:          # domingo
        return []

def generar_slots(fecha: date) -> list[time]:
    """
    Genera horarios cada PASO_MIN dentro de los bloques del día.
    IMPORTANTE: el fin es EXCLUSIVO (ultimo slot empieza antes del fin).
    Ej: 10:00–12:00 con paso 30 -> 10:00, 10:30, 11:00, 11:30
    """
    slots: list[time] = []
    delta = timedelta(minutes=PASO_MIN)
    for ini, fin in _bloques_del_dia(fecha):
        t = datetime.combine(fecha, ini)
        tfin = datetime.combine(fecha, fin)
        while t < tfin:   # fin EXCLUSIVO
            slots.append(t.time())
            t += delta
    return slots


def is_fecha_permitida(fecha: date) -> bool:
    hoy = date.today()
    return fecha >= (hoy + timedelta(days=BLOQUEO_DIAS_MIN))

def crear_o_encontrar_paciente(nombre: str, telefono: str) -> int:
    tel = normalize_tel(telefono)
    df = query_df("SELECT id FROM pacientes WHERE telefono = %s LIMIT 1", (tel,))
    if not df.empty:
        return int(df.iloc[0]["id"])
    with conn().cursor() as cur:
        cur.execute(
            "INSERT INTO pacientes(nombre, telefono) VALUES (%s, %s) RETURNING id",
            (nombre.strip(), tel),
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
        SELECT c.id AS id_cita,
               c.fecha,
               c.hora,
               p.id   AS paciente_id,
               p.nombre,
               p.telefono,
               c.nota
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

def eliminar_cita(cita_id: int) -> int:
    """Elimina la cita por ID. Devuelve el # de filas afectadas (0 o 1)."""
    with conn().cursor() as cur:
        cur.execute("DELETE FROM citas WHERE id=%s", (cita_id,))
        n = cur.rowcount or 0
    # limpia caché para que la tabla se refresque
    try:
        st.cache_data.clear()
    except Exception:
        pass
    return n

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

    # Estado inicial de sesión
    if "patient_authed" not in st.session_state:
        st.session_state.patient_authed = False
        st.session_state.patient = None

    paciente = _get_paciente()

    # Si no hay sesión válida, mostramos login/registro y paramos el render
    if not st.session_state.patient_authed or not paciente:
        modo = st.radio("¿Tienes cuenta?", ["Iniciar sesión", "Registrarme"], horizontal=True)
        if modo == "Iniciar sesión":
            with st.form("login_paciente"):
                tel = st.text_input("Teléfono")
                pw  = st.text_input("Contraseña", type="password")
                ok  = st.form_submit_button("Entrar")
            if ok:
                user = login_paciente(tel, pw)
                if user:
                    st.session_state.patient_authed = True
                    st.session_state.patient = user
                    st.success(f"Bienvenid@, {user['nombre']}")
                    st.rerun()
                else:
                    st.error("Teléfono o contraseña incorrectos.")
        else:
            with st.form("registro_paciente"):
                nombre = st.text_input("Nombre completo")
                tel    = st.text_input("Teléfono")
                pw1    = st.text_input("Contraseña", type="password")
                pw2    = st.text_input("Repite tu contraseña", type="password")
                ok     = st.form_submit_button("Crear cuenta")
            if ok:
                if not (nombre.strip() and tel.strip() and pw1 and pw2):
                    st.error("Todos los campos son obligatorios.")
                elif pw1 != pw2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        pid = registrar_paciente(nombre, tel, pw1)
                        st.session_state.patient_authed = True
                        st.session_state.patient = {"id": pid, "nombre": nombre.strip(), "telefono": normalize_tel(tel)}
                        st.success("Cuenta creada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo crear la cuenta: {e}")
        st.stop()  # <- importantísimo: no sigas renderizando si no hay sesión

    # --- Desde aquí ya hay paciente válido ---
    paciente = _get_paciente()  # refresca referencia
    nombre  = str(paciente.get("nombre", ""))
    tel     = str(paciente.get("telefono", ""))
    pid     = int(paciente.get("id"))

    st.success(f"Agendando como: {nombre} — {tel} (ID {pid})")
    if st.button("Cerrar sesión paciente"):
        st.session_state.patient_authed = False
        st.session_state.patient = None
        st.rerun()

    # ... (resto de tu flujo de selección de fecha/hora/nota y confirmación)


    min_day = date.today() + timedelta(days=BLOQUEO_DIAS_MIN)
    fecha = st.date_input("Elige el día (disponible desde el tercer día)", value=min_day, min_value=min_day)

    if not is_fecha_permitida(fecha):
        st.error("Solo puedes agendar a partir del tercer día.")
        st.stop()

    ocupados = slots_ocupados(fecha)
    libres = [t for t in generar_slots(fecha) if t not in ocupados]

    if libres:
        opciones_horas = [t.strftime("%H:%M") for t in libres]
        slot_sel = st.selectbox("Horario disponible", opciones_horas)
    else:
        slot_sel = None
        # mensaje más claro según el día
        if fecha.weekday() == 6:
            st.warning("Domingo no se agenda. Elige un día de lunes a sábado.")
        else:
            st.warning("No hay horarios libres en este día. Prueba con otra fecha.")

    nota = st.text_area("Motivo o nota (opcional)")
    confirmar = st.button("📝 Confirmar cita", disabled=(slot_sel is None))

    if confirmar:
        try:
            if slot_sel is None:
                st.error("Selecciona un horario.")
            else:
                hora = datetime.strptime(slot_sel, "%H:%M").time()
                agendar_cita_autenticado(fecha, hora, paciente_id=paciente["id"], nota=nota or None)
                st.success("¡Cita agendada! ✨")
                st.balloons()
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except pg_errors.UniqueViolation:
            st.error("Ya tienes una cita ese día. Solo se permite una por día.")
        except Exception as e:
            st.error(f"No se pudo agendar: {e}")

    # -------------------------------
    # 📌 Tu próxima cita (al fondo)
    # -------------------------------
    st.divider()
    st.subheader("📌 Tu próxima cita")

    next_df = proxima_cita_paciente(pid)

    if next_df is None or next_df.empty:
        st.info("Aún no tienes una cita próxima.")
    else:
        r = next_df.iloc[0]
        fecha_str = _fmt_fecha(r["fecha"])
        hora_str  = _fmt_hora(r["hora"])
        nota_str  = r.get("nota") or "—"
        st.success(
            f"**Folio:** {int(r['id_cita'])}  \n"
            f"**Fecha:** {fecha_str}  \n"
            f"**Hora:** {hora_str}  \n"
            f"**Nota:** {nota_str}"
        )



# ====== Vista: Carmen (Admin) ======
else:
    st.header("🧑‍⚕️ Panel de Carmen")

    # 🔐 Requiere login
    if not require_admin_auth():
        st.stop()  # no renderiza nada del panel hasta que inicie sesión


    colf, colr = st.columns([1, 2], gap="large")

    with colf:
        fecha_sel = st.date_input("Día", value=date.today(), key="fecha_admin")
        st.caption("Puedes crear citas manualmente (sin restricción de 3 días).")

        # Horarios según reglas (L–V, Sábado, Domingo cerrado)
        opts_admin = [t.strftime("%H:%M") for t in generar_slots(fecha_sel)]
        if opts_admin:
            slot = st.selectbox("Hora", opts_admin, key="hora_admin")
        else:
            slot = None
            st.info("Día no laborable o sin bloques disponibles (domingo o fuera de horario).")

        nombre = st.text_input("Nombre paciente", key="nombre_admin")
        tel = st.text_input("Teléfono", key="tel_admin")
        nota = st.text_area("Nota (opcional)", key="nota_admin")

        # 👇 Un solo botón con todas las validaciones
        if st.button("➕ Crear cita", key="crear_admin"):
            if not slot:
                st.error("Selecciona un día con horarios disponibles.")
            elif not (nombre.strip() and tel.strip()):
                st.error("Nombre y teléfono son obligatorios.")
            else:
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

    with colr:
        st.subheader(f"Citas para {fecha_sel.strftime('%d-%m-%Y')}")

        if st.button("🔄 Actualizar lista", key="refresh_admin"):
            try:
                st.cache_data.clear()
            except Exception:
                pass
            st.rerun()

        df = citas_por_dia(fecha_sel)

        # Construir tabla completa por horarios (incluye libres)
        # Normalizamos a string HH:MM para evitar choques de tipo al hacer merge
        todos_slots = pd.DataFrame({"hora": generar_slots(fecha_sel)})
        todos_slots["hora_str"] = todos_slots["hora"].map(lambda t: t.strftime("%H:%M"))

        df_m = df.copy()

        # Asegura que exista la columna 'hora' (por si viniera vacío sin columnas, raro pero posible)
        if "hora" not in df_m.columns:
            df_m["hora"] = pd.NaT

        # SIEMPRE crea 'hora_str', incluso si df_m está vacío
        df_m["hora_str"] = df_m["hora"].apply(lambda t: t.strftime("%H:%M") if pd.notna(t) else None)

        df_show = todos_slots.merge(df_m, on="hora_str", how="left")

        # Orden y columnas
        cols = ["id_cita", "paciente_id", "nombre", "telefono", "fecha", "hora", "nota"]
        for c in cols:
            if c not in df_show.columns:
                df_show[c] = None

        # Columna estado y presentación
        df_show["estado"] = df_show["id_cita"].apply(lambda x: "✅ libre" if pd.isna(x) else "🟡 ocupado")

        # Mostramos 'hora_str' como 'hora' legible primero
        df_show = df_show.rename(columns={"hora_str": "hora_txt"})
        st.dataframe(
            df_show[["hora_txt", "estado"] + cols],
            use_container_width=True
        )

        # --- Edición / eliminación solo si hay alguna ocupada ---
        if df.empty:
            st.info("No hay citas ocupadas en este día.")
        else:
            st.divider()
            st.caption("Editar / eliminar cita")

            ids = df["id_cita"].astype(int).tolist()
            cid = st.selectbox("ID cita", ids, key="cid_admin")
            r = df[df.id_cita == cid].iloc[0]

            nombre_e = st.text_input("Nombre", r["nombre"] or "", key="nombre_edit")
            tel_e = st.text_input("Teléfono", r["telefono"] or "", key="tel_edit")
            nota_e = st.text_area("Nota", r["nota"] or "", key="nota_edit")

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

            st.divider()
            st.caption("Eliminar cita seleccionada")
            cdel1, cdel2 = st.columns([1, 1])
            with cdel1:
                confirm_del = st.checkbox("Confirmar eliminación", key=f"confirm_del_{cid}")
            with cdel2:
                if st.button("🗑️ Eliminar", disabled=not confirm_del, key=f"btn_del_{cid}"):
                    try:
                        n = eliminar_cita(int(cid))
                        if n:
                            st.success("Cita eliminada.")
                        else:
                            st.info("La cita ya no existía.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo eliminar: {e}")




