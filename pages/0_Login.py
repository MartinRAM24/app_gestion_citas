import base64, hmac, hashlib, json, time, uuid
from urllib.parse import quote_plus
from modules.core import is_admin_ok, login_paciente, registrar_paciente, normalize_tel, get_app_auth_secret, ADMIN_USER
import os, streamlit as st


SECRET = get_app_auth_secret()
if not SECRET:
    st.error("Falta APP_AUTH_SECRET en Railway (Variables). Es obligatorio para iniciar sesión en producción.")
    st.stop()


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
    st.query_params["s"] = token

def get_url_token() -> str | None:
    return st.query_params.get("s")


def get_any_token() -> str | None:
    return get_url_token() or st.session_state.get("token")


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

tok = get_any_token()
if tok:
    data = verify_token(tok)
    if data:
        role = data.get("role")

        # MUY IMPORTANTE: elimina el token de la URL para evitar loop de rerun
        st.session_state["token"] = tok
        st.query_params.clear()

        if role == "admin":
            st.session_state.role = "admin"
            st.session_state.paciente = None
            st.rerun()

        elif role == "paciente":
            st.session_state.role = "paciente"
            st.session_state.paciente = {
                "id": data.get("id"),
                "nombre": data.get("nombre"),
                "telefono": data.get("tel"),
            }
            st.rerun()
# =======================
# Tabs (incluye redes)
# =======================
ENABLE_SOCIAL = True
tab_coach, tab_pac, tab_social = st.tabs(["👩‍⚕️ Coach", "🧑 Paciente", "📣 Redes"])

# ---- Coach
with tab_coach:
    st.subheader("Carmen (Coach)")
    with st.form("form_admin"):
        u = st.text_input("Usuario", value=(ADMIN_USER or "carmen"))
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar como Coach")
    if ok:
        if u and p and is_admin_ok(u, p):
            token = issue_token("admin", {"role": "admin"})
            st.session_state["token"] = token
            st.session_state.role = "admin"
            st.session_state.paciente = None
            st.query_params.clear()
            try:
                st.switch_page("pages/2_Carmen_Admin.py")
            except Exception:
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
                token = issue_token("paciente", {
                    "id": user["id"],
                    "nombre": user["nombre"],
                    "tel": user["telefono"],
                })
                st.session_state["token"] = token
                st.session_state.role = "paciente"
                st.session_state.paciente = user
                st.query_params.clear()
                try:
                    st.switch_page("pages/1_Paciente_Dashboard.py")
                except Exception:
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
                st.session_state["token"] = token
                st.session_state.role = "paciente"
                st.session_state.paciente = pac
                st.query_params.clear()
                try:
                    st.switch_page("pages/1_Paciente_Dashboard.py")
                except Exception:
                    st.rerun()
#
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






