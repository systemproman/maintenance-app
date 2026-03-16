# app.py
# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
from pathlib import Path

import streamlit as st
import arvore
import cadastro_ativos
import cadastro_pecas
from database import get_supabase


# =========================================================
# ARQUIVOS
# =========================================================
BASE_DIR = Path(__file__).parent
LOGO_FILE = BASE_DIR / "logo_fsl.png"

# tenta encontrar fundo em jpg/jpeg/png
FUNDO_FILE = None
for nome in ("fundo_fsl.jpg", "fundo_fsl.jpeg", "fundo_fsl.png"):
    candidato = BASE_DIR / nome
    if candidato.exists():
        FUNDO_FILE = candidato
        break


# =========================================================
# CONFIG DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Maintenance APP",
    page_icon=str(LOGO_FILE) if LOGO_FILE.exists() else "🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# UTILITÁRIOS
# =========================================================
def image_to_base64(path: Path) -> str:
    if not path or not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def mime_type_from_path(path: Path) -> str:
    if not path:
        return "image/png"

    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    return "image/png"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    calc = hash_password(password)
    return hmac.compare_digest(calc, password_hash)


def limpar_cache_usuarios():
    try:
        _cache_list_users.clear()
        _cache_get_user.clear()
        _cache_has_any_user.clear()
    except Exception:
        pass


# =========================================================
# CACHE DE USUÁRIOS
# =========================================================
@st.cache_data(ttl=15, show_spinner=False)
def _cache_list_users():
    supabase = get_supabase()
    resp = supabase.table("users").select("*").order("username").execute()
    return resp.data or []


@st.cache_data(ttl=15, show_spinner=False)
def _cache_get_user(username: str):
    username = str(username or "").strip().lower()
    if not username:
        return None

    supabase = get_supabase()
    resp = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


@st.cache_data(ttl=15, show_spinner=False)
def _cache_has_any_user():
    supabase = get_supabase()
    resp = supabase.table("users").select("id").limit(1).execute()
    return bool(resp.data)


# =========================================================
# REPOSITÓRIO DE USUÁRIOS
# =========================================================
class UserRepository:
    TABLE_NAME = "users"

    def __init__(self):
        self.supabase = get_supabase()

    def get_user(self, username: str):
        return _cache_get_user(username)

    def list_users(self):
        return _cache_list_users()

    def has_any_user(self):
        return _cache_has_any_user()

    def create_initial_admin(self, username: str, password: str):
        username = username.strip().lower()

        if self.has_any_user():
            return False, "Já existe pelo menos um usuário cadastrado."

        if not username:
            return False, "Informe um nome de usuário."

        if len(password) < 4:
            return False, "A senha deve ter pelo menos 4 caracteres."

        self.supabase.table(self.TABLE_NAME).insert({
            "username": username,
            "password_hash": hash_password(password),
            "role": "admin",
            "active": True,
        }).execute()

        limpar_cache_usuarios()
        return True, "Administrador inicial criado com sucesso."

    def create_user(self, username: str, password: str, role: str = "user"):
        username = username.strip().lower()

        if not username:
            return False, "Informe um nome de usuário."

        if len(password) < 4:
            return False, "A senha deve ter pelo menos 4 caracteres."

        if self.get_user(username):
            return False, "Usuário já existe."

        self.supabase.table(self.TABLE_NAME).insert({
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "active": True,
        }).execute()

        limpar_cache_usuarios()
        return True, "Usuário criado com sucesso."

    def deactivate_user(self, username: str):
        username = username.strip().lower()

        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .update({"active": False})
            .eq("username", username)
            .execute()
        )

        limpar_cache_usuarios()

        if resp.data:
            return True, "Usuário desativado com sucesso."
        return False, "Usuário não encontrado."

    def activate_user(self, username: str):
        username = username.strip().lower()

        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .update({"active": True})
            .eq("username", username)
            .execute()
        )

        limpar_cache_usuarios()

        if resp.data:
            return True, "Usuário ativado com sucesso."
        return False, "Usuário não encontrado."

    def change_password(self, username: str, new_password: str):
        username = username.strip().lower()

        if len(new_password) < 4:
            return False, "A nova senha deve ter pelo menos 4 caracteres."

        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .update({"password_hash": hash_password(new_password)})
            .eq("username", username)
            .execute()
        )

        limpar_cache_usuarios()

        if resp.data:
            return True, "Senha alterada com sucesso."
        return False, "Usuário não encontrado."

    def validate_login(self, username: str, password: str):
        user = self.get_user(username)

        if not user:
            return False, "Usuário não encontrado.", None

        if not user.get("active", True):
            return False, "Usuário inativo.", None

        if not verify_password(password, user["password_hash"]):
            return False, "Senha incorreta.", None

        return True, "Login realizado com sucesso.", user


repo = UserRepository()


# =========================================================
# SESSION STATE
# =========================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

if "pagina" not in st.session_state:
    st.session_state.pagina = ""

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None

if "perfil_logado" not in st.session_state:
    st.session_state.perfil_logado = None


# =========================================================
# CSS
# =========================================================
def aplicar_css_global():
    fundo_b64 = image_to_base64(FUNDO_FILE)
    fundo_mime = mime_type_from_path(FUNDO_FILE)

    css = """
    <style>
    html, body, [class*="css"] {
        font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
    }

    .stApp, .stApp * {
        font-family: "Inter", "Segoe UI", Arial, sans-serif !important;
    }

    #MainMenu,
    header,
    footer,
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stDeployButton"],
    [data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
    }

    html, body, .stApp, [data-testid="stAppViewContainer"], .main {
        margin: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stAppViewContainer"] > .main {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    .block-container {
        padding-top: 0.35rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stToolbar"]) {
        display: none !important;
    }

    .stAppViewBlockContainer,
    .main > div,
    .main .block-container {
        background: transparent !important;
    }

    [data-testid="stSidebar"] {
        background: rgba(10, 18, 35, 0.92) !important;
        border-right: 1px solid rgba(255,255,255,0.08) !important;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.8rem !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: rgba(255,255,255,0.92) !important;
        color: #111111 !important;
        border-radius: 12px !important;
        border: 1px solid rgba(15, 23, 42, 0.14) !important;
        box-shadow: none !important;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stSelectbox"] label {
        font-weight: 600 !important;
        color: #0f172a !important;
    }

    div[data-testid="stTextInput"] input:focus {
        border: 1px solid #0b3b60 !important;
        box-shadow: 0 0 0 0.14rem rgba(11, 59, 96, 0.18) !important;
    }

    button[title="Show password"],
    button[title="Hide password"] {
        color: #334155 !important;
    }

    .stButton > button,
    div[data-testid="stButton"] > button,
    button[kind="primary"],
    button[kind="secondary"],
    div[data-testid="baseButton-secondary"],
    div[data-testid="baseButton-primary"] {
        width: 100%;
        min-height: 42px !important;
        background-color: #0b3b60 !important;
        color: #ffffff !important;
        border: 1px solid #0b3b60 !important;
        border-radius: 12px !important;
        box-shadow: none !important;
        font-weight: 700 !important;
        transition: 0.15s ease-in-out !important;
    }

    .stButton > button:hover,
    div[data-testid="stButton"] > button:hover,
    button[kind="primary"]:hover,
    button[kind="secondary"]:hover {
        background-color: #082c47 !important;
        color: #ffffff !important;
        border: 1px solid #082c47 !important;
    }

    .stButton > button:focus,
    div[data-testid="stButton"] > button:focus {
        outline: none !important;
        box-shadow: 0 0 0 0.15rem rgba(11, 59, 96, 0.28) !important;
    }

    .stButton > button:disabled,
    div[data-testid="stButton"] > button:disabled {
        background-color: #7b8a97 !important;
        border: 1px solid #7b8a97 !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {
        background-color: #0b3b60 !important;
        color: #ffffff !important;
        border: 1px solid #0b3b60 !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: #082c47 !important;
        color: #ffffff !important;
        border: 1px solid #082c47 !important;
    }

    [data-testid="stNotification"] {
        border-radius: 10px !important;
    }
    """

    if fundo_b64:
        css += f"""
        .stApp {{
            background-image: url("data:{fundo_mime};base64,{fundo_b64}") !important;
            background-repeat: no-repeat !important;
            background-position: center center !important;
            background-attachment: fixed !important;
            background-size: cover !important;
        }}

        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            background: rgba(120, 170, 225, 0.20);
            pointer-events: none;
            z-index: 0;
        }}

        [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"] {{
            position: relative;
            z-index: 1;
        }}
        """
    else:
        css += """
        .stApp {
            background: linear-gradient(135deg, #dbeafe, #93c5fd) !important;
        }
        """

    css += """
    .login-page-space {
        height: 4vh;
        min-height: 18px;
    }

    .login-card {
        width: 100%;
        max-width: 470px;
        margin: 0 auto;
        padding: 22px 22px 18px 22px;
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.18);
        border: 1px solid rgba(255, 255, 255, 0.24);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.10);
        backdrop-filter: blur(10px) saturate(145%);
        -webkit-backdrop-filter: blur(10px) saturate(145%);
    }

    .login-title {
        text-align: center;
        font-size: 2.35rem;
        font-weight: 800;
        color: #081a44;
        margin: 0.15rem 0 0.05rem 0;
        line-height: 1.1;
    }

    .login-subtitle {
        text-align: center;
        font-size: 1rem;
        color: #314155;
        margin-bottom: 1rem;
    }

    .logo-login img {
        display: block;
        margin-left: auto;
        margin-right: auto;
        margin-bottom: 0.45rem;
        max-width: 84px !important;
        filter: drop-shadow(0 4px 12px rgba(0,0,0,0.14));
    }

    div[data-testid="stForm"] {
        margin-top: 0 !important;
        border: none !important;
        background: transparent !important;
    }

    div[data-testid="stTextInput"] {
        margin-bottom: 0.40rem !important;
    }

    div[data-testid="stTextInput"] input {
        min-height: 46px !important;
        padding-top: 0.45rem !important;
        padding-bottom: 0.45rem !important;
        font-size: 0.97rem !important;
    }

    .st-emotion-cache-uf99v8,
    .st-emotion-cache-18ni7ap,
    .st-emotion-cache-z5fcl4,
    .st-emotion-cache-h5rgaw {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    @media (max-width: 900px) {
        .login-card {
            max-width: 520px;
        }
    }

    @media (max-width: 640px) {
        .login-title {
            font-size: 2rem;
        }

        .login-card {
            padding: 18px 16px 14px 16px;
            border-radius: 18px;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# =========================================================
# TELAS
# =========================================================
def tela_primeiro_admin():
    st.info("Nenhum usuário encontrado. Crie o administrador inicial para liberar o acesso ao sistema.")

    with st.form("form_primeiro_admin", clear_on_submit=False):
        usuario_admin = st.text_input("Usuário administrador", value="admin", key="primeiro_admin_usuario")
        senha_admin = st.text_input("Senha do administrador", type="password", key="primeiro_admin_senha")
        senha_admin_2 = st.text_input("Confirmar senha", type="password", key="primeiro_admin_senha_2")

        criar = st.form_submit_button("Criar administrador inicial", use_container_width=True)

        if criar:
            if senha_admin != senha_admin_2:
                st.error("As senhas não coincidem.")
                return

            ok, msg = repo.create_initial_admin(usuario_admin, senha_admin)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def tela_login():
    st.markdown('<div class="login-page-space"></div>', unsafe_allow_html=True)

    col_esq, col_centro, col_dir = st.columns([1.6, 1, 1.6])

    with col_centro:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        if LOGO_FILE.exists():
            st.markdown('<div class="logo-login">', unsafe_allow_html=True)
            st.image(str(LOGO_FILE), width=84)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="login-title">Maintenance</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Acesso ao sistema</div>', unsafe_allow_html=True)

        if not repo.has_any_user():
            tela_primeiro_admin()
        else:
            with st.form("form_login", clear_on_submit=False):
                usuario = st.text_input("Usuário", key="login_usuario")
                senha = st.text_input("Senha", type="password", key="login_senha")
                entrar = st.form_submit_button("Entrar", use_container_width=True)

                if entrar:
                    ok, msg, user = repo.validate_login(usuario, senha)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.usuario_logado = user["username"]
                        st.session_state.perfil_logado = user["role"]
                        st.session_state.pagina = "arvore"
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown("</div>", unsafe_allow_html=True)


def tela_gerenciar_usuarios():
    st.title("Gerenciamento de Usuários")

    perfil = st.session_state.perfil_logado
    usuario_logado = st.session_state.usuario_logado

    if perfil != "admin":
        st.warning("Somente administradores podem acessar esta área.")
        return

    aba1, aba2, aba3 = st.tabs(["Criar usuário", "Listar usuários", "Alterar senha"])

    with aba1:
        st.subheader("Criar novo usuário")

        novo_usuario = st.text_input("Novo usuário", key="novo_usuario")
        nova_senha = st.text_input("Senha do novo usuário", type="password", key="nova_senha")
        novo_perfil = st.selectbox("Perfil", ["user", "admin"], key="novo_perfil")

        if st.button("Criar usuário", key="btn_criar_usuario", use_container_width=True):
            ok, msg = repo.create_user(novo_usuario, nova_senha, novo_perfil)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with aba2:
        st.subheader("Usuários cadastrados")

        users = repo.list_users()

        if not users:
            st.info("Nenhum usuário cadastrado.")
        else:
            for user in users:
                username = user["username"]
                role = user["role"]
                active = user.get("active", True)

                col1, col2, col3, col4 = st.columns([2.2, 1.2, 1.2, 1])

                with col1:
                    st.write(f"**Usuário:** {username}")
                with col2:
                    st.write(f"**Perfil:** {role}")
                with col3:
                    st.write(f"**Status:** {'Ativo' if active else 'Inativo'}")
                with col4:
                    if username != usuario_logado:
                        if active:
                            if st.button("Desativar", key=f"desativar_{username}", use_container_width=True):
                                ok, msg = repo.deactivate_user(username)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        else:
                            if st.button("Ativar", key=f"ativar_{username}", use_container_width=True):
                                ok, msg = repo.activate_user(username)
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        st.write("—")

                st.divider()

    with aba3:
        st.subheader("Alterar senha de usuário")

        users = [u["username"] for u in repo.list_users()]
        if not users:
            st.info("Nenhum usuário disponível.")
        else:
            usuario_alvo = st.selectbox("Usuário", users, key="usuario_alvo_senha")
            senha_nova = st.text_input("Nova senha", type="password", key="senha_nova_admin")

            if st.button("Alterar senha", key="btn_alterar_senha", use_container_width=True):
                ok, msg = repo.change_password(usuario_alvo, senha_nova)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


def tela_sidebar():
    if LOGO_FILE.exists():
        st.sidebar.image(str(LOGO_FILE), use_container_width=True)

    st.sidebar.markdown("## Maintenance App")
    st.sidebar.write(f"**Usuário:** {st.session_state.usuario_logado}")
    st.sidebar.write(f"**Perfil:** {st.session_state.perfil_logado}")
    st.sidebar.divider()

    if st.sidebar.button("Árvore", use_container_width=True):
        st.session_state.pagina = "arvore"

    if st.sidebar.button("Cadastro", use_container_width=True):
        st.session_state.pagina = "cadastro"

    if st.sidebar.button("Peças", use_container_width=True):
        st.session_state.pagina = "peca"

    if st.session_state.perfil_logado == "admin":
        if st.sidebar.button("Usuários", use_container_width=True):
            st.session_state.pagina = "usuarios"

    st.sidebar.divider()

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logado = False
        st.session_state.pagina = ""
        st.session_state.usuario_logado = None
        st.session_state.perfil_logado = None
        st.rerun()


def tela_principal():
    tela_sidebar()

    if st.session_state.pagina == "arvore":
        arvore.mostrar_arvore()

    elif st.session_state.pagina == "cadastro":
        cadastro_ativos.mostrar_cadastro()

    elif st.session_state.pagina == "peca":
        cadastro_pecas.menu_peca()

    elif st.session_state.pagina == "usuarios":
        tela_gerenciar_usuarios()

    else:
        st.title("Maintenance APP")
        st.write("Selecione uma opção no menu lateral.")


# =========================================================
# APP
# =========================================================
aplicar_css_global()

if not st.session_state.logado:
    tela_login()
else:
    tela_principal()