import base64, hmac, hashlib, json, time, uuid
from urllib.parse import quote_plus
from modules.core import is_admin_ok, login_paciente, registrar_paciente, normalize_tel
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

# =======================
# Config / Estilos
# =======================
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

/* Expanders / inputs / botones */
div[data-baseweb="notification"] { background-color: #800020 !important; color: #FFFFFF !important; }
h1, h2, h3, h4 { color: #111827; }
"""
st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

# =======================
# Helpers de token firmado (stateless)
# =======================
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12 horas

def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def issue_token(role: str, payload: dict) -> str:
    """
    Crea un token firmado con HMAC-SHA256.
    payload típico:
      {"role":"admin"}  ó  {"role":"paciente","id":123,"nombre":"...","tel":"..."}
    """
    now = int(time.time())
    body = {
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "nonce": uuid.uuid4().hex,
        **payload,
        "role": role,
    }
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    sig = hmac.new(SECRET.encode(), body_json, hashlib.sha256).digest()
    return f"{_b64u(body_json)}.{_b64u(sig)}"

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

def set_url_token(token: str):
    # guardamos token en la URL (?s=token)
    st.experimental_set_query_params(s=token)

def get_url_token() -> str | None:
    params = st.experimental_get_query_params()
    return params.get("s", [None])[0]

# =======================
# Branding (tu logo)
# =======================
@st.cache_data
def load_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = load_b64("assets/Logos.png")
st.markdown(
    f"""
    <div style="text-align: center;">
        <img src="data:image/png;base64,{logo_base64}" width="300">
        <p>Bienvenida/o. Elige cómo quieres entrar.</p>
    </div>
    """,
    unsafe_allow_html=True
)

# =======================
# 1) Intentar restaurar sesión desde la URL
# =======================
tok = get_url_token()
if tok:
    data = verify_token(tok)
    if data:
        role = data.get("role")
        if role == "admin":
            st.session_state.role = "admin"
            st.session_state.paciente = None
            st.switch_page("pages/2_Carmen_Admin.py")
        elif role == "paciente":
            # payload mínimo para el dashboard
            st.session_state.role = "paciente"
            st.session_state.paciente = {
                "id": data.get("id"),
                "nombre": data.get("nombre"),
                "telefono": data.get("tel"),
            }
            st.switch_page("pages/1_Paciente_Dashboard.py")

# =======================
# 2) Estado base (si no hay token válido)
# =======================
st.session_state.setdefault("role", None)
st.session_state.setdefault("paciente", None)

# Redirección si ya hay sesión en memoria (fallback)
role = st.session_state.get("role")
if role == "admin":
    st.switch_page("pages/2_Carmen_Admin.py")
elif role == "paciente" and st.session_state.get("paciente"):
    st.switch_page("pages/1_Paciente_Dashboard.py")

# =======================
# Tabs (incluye redes)
# =======================
ENABLE_SOCIAL = True
tab_coach, tab_pac, tab_social = st.tabs(["👩‍⚕️ Coach", "🧑 Paciente", "📣 Redes"])

# ---- Coach
with tab_coach:
    st.subheader("Carmen (Coach)")
    with st.form("form_admin"):
        st.text_input("Usuario", value="Carmen", disabled=True)
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar como Coach")
    if ok:
        if p and is_admin_ok("Carmen", p):
            # emitimos token y lo ponemos en URL
            token = issue_token("admin", {"role": "admin"})
            set_url_token(token)
            st.session_state.role = "admin"
            st.session_state.paciente = None
            st.rerun()
        else:
            st.error("Credenciales inválidas.")

# ---- Paciente
with tab_pac:
    st.subheader("Paciente")
    modo = st.radio("Cuenta", ["Iniciar sesión", "Registrarme"], horizontal=True, key="pac_modo")

    if modo == "Iniciar sesión":
        with st.form("form_login"):
            tel = st.text_input("Teléfono")
            pw  = st.text_input("Contraseña", type="password")
            ok  = st.form_submit_button("Entrar")
        if ok:
            user = login_paciente(tel, pw)
            if user:
                # user esperado: {"id":..., "nombre":..., "telefono": ...}
                token = issue_token("paciente", {
                    "id": user.get("id"),
                    "nombre": user.get("nombre"),
                    "tel": user.get("telefono"),
                })
                set_url_token(token)
                st.session_state.role = "paciente"
                st.session_state.paciente = user
                st.rerun()
            else:
                st.error("Teléfono o contraseña incorrectos.")
    else:
        with st.form("form_reg"):
            nombre = st.text_input("Nombre completo")
            tel    = st.text_input("Teléfono")
            pw1    = st.text_input("Contraseña", type="password")
            pw2    = st.text_input("Repite tu contraseña", type="password")
            ok     = st.form_submit_button("Registrarme")
        if ok:
            if not (nombre.strip() and tel.strip() and pw1 and pw2):
                st.error("Completa todos los campos.")
            elif pw1 != pw2:
                st.error("Las contraseñas no coinciden.")
            else:
                pid = registrar_paciente(nombre, tel, pw1)
                pac = {"id": pid, "nombre": nombre.strip(), "telefono": normalize_tel(tel)}
                token = issue_token("paciente", {
                    "id": pac["id"], "nombre": pac["nombre"], "tel": pac["telefono"],
                })
                set_url_token(token)
                st.session_state.role = "paciente"
                st.session_state.paciente = pac
                st.rerun()

# ---- 📣 Redes
with tab_social:
    if ENABLE_SOCIAL:
        st.subheader("Conecta con Carmen")
        @st.cache_data
        def _load_icon(p):
            with open(p, "rb") as f: return base64.b64encode(f.read()).decode()
        ig_b64  = _load_icon("assets/ig.png")
        ttk_b64 = _load_icon("assets/tiktok.png")
        wa_b64  = _load_icon("assets/wa.png")

        IG_URL = "https://www.instagram.com/carmen._ochoa?igsh=dnd2aGt5a25xYTg0"
        TTK_PROFILE_URL = "https://www.tiktok.com/@carmen_ochoa123?_t=ZS-907SiUuhJDw&_r=1"
        TTK_VIDEO_ID = "7521784372152831240"
        TTK_EMBED_URL = f"https://www.tiktok.com/embed/v2/{TTK_VIDEO_ID}"

        WA_NUMBER = "523511974405"
        WA_TEXT = "Hola Carmen, quiero una consulta."
        wa_link = f"https://wa.me/{WA_NUMBER}?text={quote_plus(WA_TEXT)}"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""<a href="{IG_URL}" target="_blank" rel="noopener">
                <img src="data:image/png;base64,{ig_b64}" style="width:120px;border-radius:12px;display:block;margin:0 auto;cursor:pointer;">
            </a>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<a href="{TTK_PROFILE_URL}" target="_blank" rel="noopener">
                <img src="data:image/png;base64,{ttk_b64}" style="width:120px;border-radius:12px;display:block;margin:0 auto;cursor:pointer;">
            </a>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<a href="{wa_link}" target="_blank" rel="noopener">
                <img src="data:image/png;base64,{wa_b64}" style="width:120px;border-radius:12px;display:block;margin:0 auto;cursor:pointer;">
            </a>""", unsafe_allow_html=True)

        st.markdown("---")
        st.caption("🎥 Video destacado de TikTok")
        show_video = st.toggle("Mostrar video", value=False, key="show_tiktok_embed")
        if show_video:
            st.components.v1.html(
                f"""<div style="display:flex;justify-content:center;">
                        <iframe src="{TTK_EMBED_URL}" width="350" height="600" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>
                    </div>""",
                height=650,
            )
        else:
            st.link_button("Abrir video en TikTok", f"https://www.tiktok.com/@carmen_ochoa123/video/{TTK_VIDEO_ID}")
    else:
        st.info("⚡ Sección de redes desactivada temporalmente")






