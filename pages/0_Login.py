import streamlit as st
from modules.core import is_admin_ok, login_paciente, registrar_paciente, normalize_tel
import base64
from urllib.parse import quote_plus

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

/* Expanders / inputs / botones... (tu CSS actual) */
div[data-baseweb="notification"] { background-color: #800020 !important; color: #FFFFFF !important; }
h1, h2, h3, h4 { color: #111827; }
"""

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

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

# Estado base
st.session_state.setdefault("role", None)
st.session_state.setdefault("paciente", None)

# Redirección si ya hay sesión
role = st.session_state.get("role")
if role == "admin":
    st.switch_page("pages/2_Carmen_Admin.py")
elif role == "paciente" and st.session_state.get("paciente"):
    st.switch_page("pages/1_Paciente_Dashboard.py")

# =========================
# Tabs (agregamos 📣 Redes)
# =========================
ENABLE_SOCIAL = True   # cambia a True si lo quieres activar

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
            st.session_state.role = "admin"
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
                st.session_state.role = "paciente"
                st.session_state.paciente = {
                    "id": pid, "nombre": nombre.strip(), "telefono": normalize_tel(tel)
                }
                st.rerun()

# ---- 📣 Redes (a la derecha)
with tab_social:
    if ENABLE_SOCIAL:
        st.subheader("Conecta con Carmen")

        # Base64 de iconos (si ya tienes load_b64 arriba, esto va perfecto)
        ig_b64 = load_b64("assets/ig.png")
        ttk_b64 = load_b64("assets/tiktok.png")
        wa_b64 = load_b64("assets/wa.png")

        # Links
        IG_URL = "https://www.instagram.com/carmen._ochoa?igsh=dnd2aGt5a25xYTg0"
        TTK_PROFILE_URL = "https://www.tiktok.com/@carmen_ochoa123?_t=ZS-907SiUuhJDw&_r=1"
        TTK_VIDEO_ID = "7521784372152831240"
        TTK_EMBED_URL = f"https://www.tiktok.com/embed/v2/{TTK_VIDEO_ID}"

        WA_NUMBER = "523511974405"  # 52 + número sin signos
        WA_TEXT = "Hola Carmen, quiero una consulta."
        wa_link = f"https://wa.me/{WA_NUMBER}?text={quote_plus(WA_TEXT)}"

        # Fila de iconos clicables
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"""
                    <a href="{IG_URL}" target="_blank" rel="noopener">
                      <img src="data:image/png;base64,{ig_b64}"
                           alt="Instagram"
                           style="width:120px; border-radius:12px; display:block; margin:0 auto; cursor:pointer;">
                    </a>
                    """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                    <a href="{TTK_PROFILE_URL}" target="_blank" rel="noopener">
                      <img src="data:image/png;base64,{ttk_b64}"
                           alt="TikTok"
                           style="width:120px; border-radius:12px; display:block; margin:0 auto; cursor:pointer;">
                    </a>
                    """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""
                    <a href="{wa_link}" target="_blank" rel="noopener">
                      <img src="data:image/png;base64,{wa_b64}"
                           alt="WhatsApp"
                           style="width:120px; border-radius:12px; display:block; margin:0 auto; cursor:pointer;">
                    </a>
                    """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.caption("🎥 Video destacado de TikTok")

        # ⚡ Render perezoso: solo carga el iFrame si el usuario lo pide
        show_video = st.toggle("Mostrar video", value=False, key="show_tiktok_embed")
        if show_video:
            st.components.v1.html(
                f"""
                    <div style="display:flex; justify-content:center;">
                        <iframe src="{TTK_EMBED_URL}"
                                width="350" height="600" frameborder="0"
                                allow="autoplay; encrypted-media"
                                allowfullscreen></iframe>
                    </div>
                    """,
                height=650,
            )
        else:
            # Alternativa ligera cuando el iFrame no está cargado
            st.link_button("Abrir video en TikTok", f"https://www.tiktok.com/@carmen_ochoa123/video/{TTK_VIDEO_ID}")

    else:
        st.info("⚡ Sección de redes desactivada temporalmente")





