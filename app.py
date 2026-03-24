# app.py
# -*- coding: utf-8 -*-

import base64
import hashlib
import hmac
import time
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
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def logo_to_data_url(path: Path) -> str:
    if not path or not path.exists():
        return ""
    mime = mime_type_from_path(path)
    b64 = image_to_base64(path)
    return f"data:{mime};base64,{b64}"


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


def navegar_para(pagina_destino: str):
    if st.session_state.pagina != pagina_destino:
        st.session_state.pagina = pagina_destino
        st.session_state._mostrar_splash = True
        st.rerun()


def mostrar_splash_transicao():
    logo_data_url = logo_to_data_url(LOGO_FILE)
    if not logo_data_url:
        return

    st.markdown(
        f"""
        <style>
        .fsl-splash-overlay {{
            position: fixed;
            inset: 0;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
                radial-gradient(circle at center, rgba(255,255,255,0.97) 0%, rgba(245,247,250,0.98) 45%, rgba(232,238,245,0.99) 100%);
            animation: fslSplashFade 0.90s ease forwards;
            pointer-events: none;
        }}

        .fsl-splash-logo {{
            width: 220px;
            max-width: 42vw;
            opacity: 0;
            transform: scale(1.45);
            filter: drop-shadow(0 18px 34px rgba(0,0,0,0.16));
            animation: fslSplashLogo 0.90s cubic-bezier(.2,.8,.2,1) forwards;
        }}

        @keyframes fslSplashLogo {{
            0% {{
                opacity: 0;
                transform: scale(1.45);
            }}
            18% {{
                opacity: 1;
                transform: scale(1.18);
            }}
            100% {{
                opacity: 0;
                transform: scale(0.72);
            }}
        }}

        @keyframes fslSplashFade {{
            0%, 82% {{
                opacity: 1;
                visibility: visible;
            }}
            100% {{
                opacity: 0;
                visibility: hidden;
            }}
        }}

        @media (max-width: 640px) {{
            .fsl-splash-logo {{
                width: 160px;
            }}
        }}
        </style>

        <div class="fsl-splash-overlay">
            <img class="fsl-splash-logo" src="{logo_data_url}" alt="Logo" />
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# CACHE DE USUÁRIOS
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def _cache_list_users():
    supabase = get_supabase()
    resp = supabase.table("users").select("*").order("username").execute()
    return resp.data or []


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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
def inicializar_estado():
    padrao = {
        "logado": False,
        "pagina": "",
        "usuario_logado": None,
        "perfil_logado": None,
        "_mostrar_splash": False,
    }

    for chave, valor in padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


inicializar_estado()


# =========================================================
# CSS
# =========================================================
def aplicar_css_global():
    fundo_b64 = image_to_base64(FUNDO_FILE)
    fundo_mime = mime_type_from_path(FUNDO_FILE)

    usa_fundo = bool(fundo_b64)

    background_css = f"""
        background:
            linear-gradient(rgba(247, 250, 252, 0.78), rgba(247, 250, 252, 0.78)),
            url("data:{fundo_mime};base64,{fundo_b64}") center center / cover no-repeat fixed;
    """ if usa_fundo else """
        background: linear-gradient(135deg, #eef3f9 0%, #dfe9f5 100%);
    """

    css = f"""
    <style>
    * {{
        box-sizing: border-box !important;
    }}

    html, body, [data-testid="stAppViewContainer"], .stApp {{
        {background_css}
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    .block-container,
    .main .block-container,
    .stAppViewBlockContainer,
    [data-testid="stAppViewContainer"] .main,
    section.main {{
        padding-left: 1.20rem !important;
        padding-right: 1.20rem !important;
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }}

    .stAppViewBlockContainer,
    .main > div,
    .main .block-container,
    section.main,
    [data-testid="stAppViewContainer"] > .main {{
        background: transparent !important;
    }}

    [data-testid="stSidebar"] {{
        background: rgba(10, 18, 35, 0.92) !important;
        border-right: 1px solid rgba(255,255,255,0.08) !important;
    }}

    section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.8rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}

    div[data-testid="stTextInput"],
    div[data-testid="stTextArea"],
    div[data-testid="stNumberInput"],
    div[data-testid="stSelectbox"],
    div[data-testid="stDateInput"],
    div[data-testid="stTimeInput"],
    div[data-testid="stFileUploader"] {{
        padding: 0 !important;
        margin-bottom: 0.55rem !important;
    }}

    div[data-testid="stTextInput"] > div,
    div[data-testid="stTextArea"] > div,
    div[data-testid="stNumberInput"] > div,
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stDateInput"] > div,
    div[data-testid="stTimeInput"] > div {{
        overflow: visible !important;
    }}

    div[data-testid="stTextInput"] > div > div > input,
    div[data-testid="stNumberInput"] > div > div > input,
    div[data-testid="stTextArea"] textarea,
    div[data-baseweb="select"] > div,
    div[data-testid="stDateInput"] input,
    div[data-testid="stTimeInput"] input {{
        min-height: 48px !important;
        padding: 0.72rem 0.95rem !important;
        border-radius: 14px !important;
        border: 1px solid rgba(15, 23, 42, 0.16) !important;
        background: rgba(255,255,255,0.96) !important;
        color: #111111 !important;
        box-shadow: none !important;
        line-height: 1.2 !important;
    }}

    div[data-testid="stTextArea"] textarea {{
        min-height: 120px !important;
        padding-top: 0.85rem !important;
        padding-bottom: 0.85rem !important;
        resize: vertical !important;
    }}

    div[data-testid="stTextInput"] input[type="password"],
    div[data-testid="stTextInput"] input[type="text"] {{
        padding-right: 2.75rem !important;
    }}

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stNumberInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stDateInput"] input:focus,
    div[data-testid="stTimeInput"] input:focus {{
        border: 1px solid #0b3b60 !important;
        box-shadow: 0 0 0 0.14rem rgba(11, 59, 96, 0.18) !important;
    }}

    button[title="Show password"],
    button[title="Hide password"] {{
        width: 34px !important;
        height: 34px !important;
        min-width: 34px !important;
        min-height: 34px !important;
        padding: 0 !important;
        border-radius: 10px !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #334155 !important;
    }}

    button[title="Show password"]:hover,
    button[title="Hide password"]:hover {{
        background: rgba(15, 23, 42, 0.06) !important;
    }}

    .stButton > button,
    div[data-testid="stButton"] > button,
    button[kind="primary"],
    button[kind="secondary"],
    div[data-testid="stFormSubmitButton"] > button {{
        width: 100%;
        min-height: 44px !important;
        background-color: #0b3b60 !important;
        color: #ffffff !important;
        border: 1px solid #0b3b60 !important;
        border-radius: 12px !important;
        box-shadow: none !important;
        font-weight: 700 !important;
        transition: none !important;
    }}

    .stButton > button:hover,
    div[data-testid="stButton"] > button:hover,
    button[kind="primary"]:hover,
    button[kind="secondary"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {{
        background-color: #082c47 !important;
        color: #ffffff !important;
        border: 1px solid #082c47 !important;
    }}

    .stButton > button:focus,
    .stButton > button:focus-visible,
    div[data-testid="stButton"] > button:focus,
    div[data-testid="stButton"] > button:focus-visible,
    div[data-testid="stFormSubmitButton"] > button:focus,
    div[data-testid="stFormSubmitButton"] > button:focus-visible {{
        outline: none !important;
        box-shadow: 0 0 0 0.15rem rgba(11, 59, 96, 0.28) !important;
    }}

    .stButton > button:active,
    div[data-testid="stButton"] > button:active,
    div[data-testid="stFormSubmitButton"] > button:active {{
        background-color: #082c47 !important;
        color: #ffffff !important;
        border: 1px solid #082c47 !important;
        box-shadow: none !important;
    }}

    .stButton > button:disabled,
    div[data-testid="stButton"] > button:disabled,
    div[data-testid="stFormSubmitButton"] > button:disabled {{
        background-color: #7b8a97 !important;
        border: 1px solid #7b8a97 !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }}

    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {{
        width: 100% !important;
        min-height: 42px !important;
        background: #0b3b60 !important;
        background-color: #0b3b60 !important;
        color: #ffffff !important;
        border: 1px solid #0b3b60 !important;
        border-radius: 12px !important;
        box-shadow: none !important;
        font-weight: 700 !important;
        transition: none !important;
        transform: none !important;
        filter: none !important;
        background-image: none !important;
    }}

    [data-testid="stSidebar"] .stButton > button:hover,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {{
        background: #082c47 !important;
        background-color: #082c47 !important;
        color: #ffffff !important;
        border: 1px solid #082c47 !important;
        box-shadow: none !important;
    }}

    [data-testid="stSidebar"] .stButton > button:disabled,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled {{
        background: #6b7280 !important;
        background-color: #6b7280 !important;
        color: #ffffff !important;
        border: 1px solid #6b7280 !important;
        opacity: 1 !important;
    }}

    .login-page-space {{
        height: 3vh;
    }}

    .login-card {{
        width: 100%;
        max-width: 470px;
        margin: 0 auto;
        padding: 22px 22px 18px 22px;
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.20);
        border: 1px solid rgba(255, 255, 255, 0.24);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.10);
        backdrop-filter: blur(10px) saturate(145%);
        -webkit-backdrop-filter: blur(10px) saturate(145%);
    }}

    .login-title {{
        text-align: center;
        font-size: 2.35rem;
        font-weight: 800;
        color: #081a44;
        margin: 0.15rem 0 0.05rem 0;
        line-height: 1.1;
    }}

    .login-subtitle {{
        text-align: center;
        font-size: 1rem;
        color: #314155;
        margin-bottom: 1rem;
    }}

    .logo-login img {{
        display: block;
        margin-left: auto;
        margin-right: auto;
        margin-bottom: 0.45rem;
        max-width: 84px !important;
        filter: drop-shadow(0 4px 12px rgba(0,0,0,0.14));
    }}

    div[data-testid="stForm"] {{
        margin-top: 0 !important;
        border: none !important;
        background: transparent !important;
    }}

    @media (max-width: 640px) {{
        .login-title {{
            font-size: 2rem;
        }}

        .login-card {{
            padding: 18px 16px 14px 16px;
            border-radius: 18px;
        }}

        .block-container,
        .main .block-container,
        .stAppViewBlockContainer,
        [data-testid="stAppViewContainer"] .main,
        section.main {{
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
        }}
    }}
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
                        st.session_state._mostrar_splash = True
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
        navegar_para("arvore")

    if st.sidebar.button("Cadastro equipamentos", use_container_width=True):
        navegar_para("cadastro")

    if st.sidebar.button("Peças", use_container_width=True):
        navegar_para("peca")

    if st.session_state.perfil_logado == "admin":
        if st.sidebar.button("Usuários", use_container_width=True):
            navegar_para("usuarios")

    st.sidebar.divider()

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.logado = False
        st.session_state.pagina = ""
        st.session_state.usuario_logado = None
        st.session_state.perfil_logado = None
        st.session_state._mostrar_splash = False
        st.rerun()


def tela_principal():
    tela_sidebar()

    if st.session_state.get("_mostrar_splash", False):
        mostrar_splash_transicao()
        st.session_state._mostrar_splash = False
        time.sleep(0.08)

    pagina = st.session_state.pagina or "arvore"

    if pagina == "arvore":
        arvore.mostrar_arvore()
    elif pagina == "cadastro":
        cadastro_ativos.mostrar_cadastro()
    elif pagina == "peca":
        cadastro_pecas.menu_peca()
    elif pagina == "usuarios":
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
