import streamlit as st
from modules.core import is_admin_ok, login_paciente, registrar_paciente, normalize_tel
import base64

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

def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

logo_base64 = get_base64_of_bin_file("assets/Logo.png")

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
tab_admin, tab_pac, tab_social = st.tabs(["👩‍⚕️ Coach", "🧑 Paciente", "📣 Redes"])

# ---- Coach
with tab_admin:
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
    st.subheader("Conecta con Carmen")

    # Links
    IG_URL = "https://www.instagram.com/carmen._ochoa?igsh=dnd2aGt5a25xYTg0"
    TTK_PROFILE_URL = "https://www.tiktok.com/@carmen_ochoa123?_t=ZS-907SiUuhJDw&_r=1"
    TTK_VIDEO_URL = "https://vt.tiktok.com/ZSDnmFBK2/"
    # WhatsApp: ajusta el prefijo país si hace falta (52 = México)
    WA_NUMBER = "523511974405"
    WA_TEXT = "Hola Coach Carmen, vengo de tu web y me gustaría agendar una cita."
    WA_URL = f"https://wa.me/{WA_NUMBER}?text={st.utils._quote(WA_TEXT)}"

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""
            <a href="{IG_URL}" target="_blank" rel="noopener">
                <img src="assets/ig.png" style="width:120px; border-radius:12px;">
            </a>
            <div style="margin-top:6px; text-align:center;"><a href="{IG_URL}" target="_blank">Instagram</a></div>
            """,
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""
            <a href="{TTK_PROFILE_URL}" target="_blank" rel="noopener">
                <img src="assets/tiktok.png" style="width:120px; border-radius:12px;">
            </a>
            <div style="margin-top:6px; text-align:center;"><a href="{TTK_PROFILE_URL}" target="_blank">TikTok</a></div>
            """,
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"""
            <a href="{WA_URL}" target="_blank" rel="noopener">
                <img src="assets/wa.png" style="width:120px; border-radius:12px;">
            </a>
            <div style="margin-top:6px; text-align:center;"><a href="{WA_URL}" target="_blank">WhatsApp</a></div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.caption("Video destacado de TikTok")

    # Embed simple del video de TikTok (si no carga, muestra un link)
    try:
        st.components.v1.html(
            f"""
            <blockquote class="tiktok-embed" cite="{TTK_VIDEO_URL}" data-video-id="" style="max-width: 605px; min-width: 325px;">
              <section> <a target="_blank" href="{TTK_VIDEO_URL}">Ver en TikTok</a> </section>
            </blockquote>
            <script async src="https://www.tiktok.com/embed.js"></script>
            """,
            height=680,
        )
    except Exception:
        st.link_button("Ver video en TikTok", TTK_VIDEO_URL)


