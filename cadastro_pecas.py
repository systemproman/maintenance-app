import streamlit as st
import pandas as pd
from io import BytesIO

from database import SupabasePartRepository


class PecaRepository:
    def listar(self):
        raise NotImplementedError

    def adicionar(self, nova_peca):
        raise NotImplementedError

    def atualizar(self, codigo, dados_atualizados):
        raise NotImplementedError

    def excluir(self, codigo):
        raise NotImplementedError

    def buscar_por_codigo(self, codigo):
        raise NotImplementedError


class SupabasePecaRepositoryAdapter(PecaRepository):
    def __init__(self):
        self.repo = SupabasePartRepository()

    def listar(self):
        return self.repo.list_parts()

    def adicionar(self, nova_peca):
        self.repo.create_part(nova_peca)

    def atualizar(self, codigo, dados_atualizados):
        return self.repo.update_part(codigo, dados_atualizados)

    def excluir(self, codigo):
        return self.repo.delete_part(codigo)

    def buscar_por_codigo(self, codigo):
        return self.repo.get_part_by_code(codigo)


repo = SupabasePecaRepositoryAdapter()


# ==========================================================
# ESTILO GLOBAL
# ==========================================================

def aplicar_estilo_pecas():
    st.markdown(
        """
        <style>
        .stApp {
            background: #ffffff !important;
            color: #000000 !important;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background: #ffffff !important;
            color: #000000 !important;
        }

        .main, .block-container {
            background: #ffffff !important;
            color: #000000 !important;
            padding-top: 1rem !important;
        }

        section[data-testid="stSidebar"] {
            background: #ffffff !important;
            color: #000000 !important;
        }

        div[data-testid="stToolbar"] {
            background: #ffffff !important;
        }

        label, p, div, span, h1, h2, h3, h4, h5, h6 {
            color: #000000 !important;
        }

        h1, h2, h3 {
            font-family: Consolas, "Courier New", monospace !important;
            font-weight: 700 !important;
            letter-spacing: 0.2px !important;
        }

        div[data-testid="stTextInput"] > div > div > input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] input {
            border: 2px solid #c97a00 !important;
            border-radius: 12px !important;
            background: #fffdf7 !important;
            color: #000000 !important;
            box-shadow: 0 0 0 2px rgba(201, 122, 0, 0.10) !important;
            font-weight: 700 !important;
            font-family: Consolas, "Courier New", monospace !important;
        }

        div[data-testid="stTextInput"] > div > div > input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stNumberInput"] input:focus {
            border: 2px solid #ff8c00 !important;
            box-shadow: 0 0 0 4px rgba(255, 140, 0, 0.18) !important;
        }

        div[data-testid="stTextInput"] > div > div > input::placeholder,
        div[data-testid="stTextArea"] textarea::placeholder {
            color: #7a5a20 !important;
            opacity: 1 !important;
            font-weight: 700 !important;
        }

        .stSelectbox label,
        .stTextInput label,
        .stTextArea label,
        .stNumberInput label,
        .stFileUploader label,
        .stToggle label {
            font-family: Consolas, "Courier New", monospace !important;
            font-weight: 700 !important;
            color: #000000 !important;
        }

        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {
            background: #f7f7f7 !important;
            color: #000000 !important;
            border: 2px solid #d6d6d6 !important;
            border-radius: 12px !important;
            font-family: Consolas, "Courier New", monospace !important;
            font-weight: 700 !important;
            min-height: 42px !important;
            transition: 0.15s ease !important;
            box-shadow: none !important;
        }

        div.stButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            background: #eeeeee !important;
            color: #000000 !important;
            border-color: #c5c5c5 !important;
        }

        div.stButton > button[kind="primary"] {
            background: #FFA500 !important;
            color: #000000 !important;
            border: 2px solid #c97a00 !important;
        }

        div.stButton > button[kind="primary"]:hover {
            background: #ffb733 !important;
            color: #000000 !important;
            border-color: #c97a00 !important;
        }

        div.stButton > button:disabled,
        div[data-testid="stDownloadButton"] > button:disabled {
            background: #f1f1f1 !important;
            color: #9a9a9a !important;
            border: 2px solid #e0e0e0 !important;
            opacity: 1 !important;
            cursor: not-allowed !important;
        }

        div.stButton > button[kind="primary"]:disabled {
            background: #f7dfb7 !important;
            color: #9a8561 !important;
            border: 2px solid #ead0a4 !important;
            opacity: 1 !important;
            cursor: not-allowed !important;
        }

        .stDataFrame, .stTable {
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# ==========================================================
# UTILITÁRIOS
# ==========================================================

def gerar_codigo_peca(lista_pecas):
    numeros = [
        int(p["codigo"].split("-")[1])
        for p in lista_pecas
        if "codigo" in p
        and str(p["codigo"]).startswith("PC-")
        and len(str(p["codigo"]).split("-")) > 1
        and str(p["codigo"]).split("-")[1].isdigit()
    ]

    if not numeros:
        return "PC-0001"

    return f"PC-{max(numeros) + 1:04d}"


def filtrar_pecas(lista_pecas, busca):
    if not busca.strip():
        return lista_pecas

    busca = busca.strip().upper()

    return [
        p for p in lista_pecas
        if busca in str(p.get("codigo", "")).upper()
        or busca in str(p.get("descricao", "")).upper()
        or busca in str(p.get("referencia", "")).upper()
        or busca in str(p.get("fabricante", "")).upper()
        or busca in str(p.get("observacoes", "")).upper()
    ]


def gerar_excel(lista_pecas):
    df = pd.DataFrame(lista_pecas)

    if df.empty:
        df = pd.DataFrame(columns=["codigo", "descricao", "referencia", "fabricante", "observacoes"])

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Peças")
        ws = writer.sheets["Peças"]

        larguras = {
            "A": 14,
            "B": 35,
            "C": 25,
            "D": 25,
            "E": 45,
        }

        for coluna, largura in larguras.items():
            ws.column_dimensions[coluna].width = largura

    output.seek(0)
    return output


def normalizar_texto(valor):
    return str(valor or "").strip().upper()


def inicializar_estado():
    if "acao" not in st.session_state:
        st.session_state.acao = ""

    if "codigo_selecionado" not in st.session_state:
        st.session_state.codigo_selecionado = ""

    if "select_codigo" not in st.session_state:
        st.session_state.select_codigo = ""

    if "busca_lista" not in st.session_state:
        st.session_state.busca_lista = ""

    if "resetar_select_peca" not in st.session_state:
        st.session_state.resetar_select_peca = False

    if "proximo_select_peca" not in st.session_state:
        st.session_state.proximo_select_peca = ""


def limpar_modo(limpar_selecao=False):
    st.session_state.acao = ""

    if limpar_selecao:
        st.session_state.codigo_selecionado = ""
        st.session_state.resetar_select_peca = True

    st.rerun()


def montar_select_pecas(lista_pecas):
    opcoes = {"": ""}
    for peca in lista_pecas:
        codigo = peca.get("codigo", "")
        descricao = peca.get("descricao", "")
        if codigo:
            opcoes[codigo] = f"{codigo} - {descricao}" if descricao else codigo
    return opcoes


# ==========================================================
# FORMULÁRIO
# ==========================================================

def construir_formulario_peca(peca_edicao=None, codigo_novo=""):
    editando = peca_edicao is not None

    codigo = peca_edicao.get("codigo", "") if editando else codigo_novo
    descricao = peca_edicao.get("descricao", "") if editando else ""
    referencia = peca_edicao.get("referencia", "") if editando else ""
    fabricante = peca_edicao.get("fabricante", "") if editando else ""
    observacoes = peca_edicao.get("observacoes", "") if editando else ""

    col1, col2 = st.columns([15, 5])

    with col1:
        descricao = st.text_input("Descrição", value=descricao, key="form_descricao_peca")

    with col2:
        st.text_input("Código", value=codigo, disabled=True, key="form_codigo_peca")

    col3, col4 = st.columns(2)

    with col3:
        referencia = st.text_input("Referência", value=referencia, key="form_referencia_peca")

    with col4:
        fabricante = st.text_input("Fabricante", value=fabricante, key="form_fabricante_peca")

    observacoes = st.text_area(
        "Observações",
        value=observacoes,
        key="form_observacoes_peca",
        placeholder="Campo não obrigatório"
    )

    return {
        "codigo": normalizar_texto(codigo),
        "descricao": normalizar_texto(descricao),
        "referencia": normalizar_texto(referencia),
        "fabricante": normalizar_texto(fabricante),
        "observacoes": observacoes.strip(),
    }


# ==========================================================
# TELAS
# ==========================================================

def tela_nova_peca(lista_pecas):
    st.subheader("Nova peça")

    codigo_novo = gerar_codigo_peca(lista_pecas)
    dados = construir_formulario_peca(codigo_novo=codigo_novo)

    if st.button("Salvar", key="btn_salvar_nova_peca", type="primary", use_container_width=True):
        if not dados["descricao"]:
            st.error("A descrição é obrigatória.")
            return

        repo.adicionar(dados)

        st.session_state.acao = ""
        st.session_state.codigo_selecionado = ""
        st.session_state.resetar_select_peca = True
        st.rerun()


def tela_editar_peca():
    st.subheader("Editar peça")

    codigo = st.session_state.codigo_selecionado
    peca = repo.buscar_por_codigo(codigo)

    if not codigo:
        st.error("Selecione uma peça cadastrada para editar.")
        return

    if not peca:
        st.error("Peça não encontrada.")
        return

    dados = construir_formulario_peca(peca_edicao=peca)

    if st.button("Salvar edição", key="btn_salvar_edicao_peca", type="primary", use_container_width=True):
        if not dados["descricao"]:
            st.error("A descrição é obrigatória.")
            return

        repo.atualizar(
            codigo,
            {
                "descricao": dados["descricao"],
                "referencia": dados["referencia"],
                "fabricante": dados["fabricante"],
                "observacoes": dados["observacoes"],
            }
        )

        st.session_state.acao = ""
        st.session_state.codigo_selecionado = dados["codigo"]
        st.session_state.proximo_select_peca = dados["codigo"]
        st.rerun()


def tela_excluir_peca():
    st.subheader("Excluir peça")

    codigo = st.session_state.codigo_selecionado
    peca = repo.buscar_por_codigo(codigo)

    if not codigo:
        st.error("Selecione uma peça cadastrada para excluir.")
        return

    if not peca:
        st.error("Peça não encontrada.")
        return

    st.warning(f"Confirma a exclusão da peça {peca['codigo']} - {peca['descricao']}?")

    if st.button("Confirmar exclusão", key="btn_confirmar_exclusao_peca", type="primary", use_container_width=True):
        repo.excluir(codigo)
        st.session_state.acao = ""
        st.session_state.codigo_selecionado = ""
        st.session_state.resetar_select_peca = True
        st.rerun()


def exibir_tabela_pecas(lista_pecas):
    st.subheader("Tabela de peças")

    if not lista_pecas:
        st.info("Nenhuma peça cadastrada.")
        return

    busca_lista = st.text_input(
        "Buscar por código, descrição, referência, fabricante ou observações",
        key="busca_lista",
        placeholder="Digite para filtrar a lista"
    )

    lista_filtrada = filtrar_pecas(lista_pecas, busca_lista)

    st.caption(f"{len(lista_filtrada)} peça(s) encontrada(s).")

    if lista_filtrada:
        df = pd.DataFrame(lista_filtrada)

        colunas_esperadas = ["codigo", "descricao", "referencia", "fabricante", "observacoes"]
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = ""

        df = df[colunas_esperadas]
        df.columns = ["CÓDIGO", "DESCRIÇÃO", "REFERÊNCIA", "FABRICANTE", "OBSERVAÇÕES"]

        st.dataframe(df, use_container_width=True, hide_index=True)

        arquivo_excel = gerar_excel(lista_filtrada)

        st.download_button(
            label="📗 Exportar lista em XLSX",
            data=arquivo_excel,
            file_name="pecas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info("Nenhuma peça encontrada.")


def tela_cadastro(lista_pecas):
    opcoes_select = montar_select_pecas(lista_pecas)
    lista_codigos = list(opcoes_select.keys())

    if st.session_state.resetar_select_peca:
        st.session_state.select_codigo = ""
        st.session_state.codigo_selecionado = ""
        st.session_state.resetar_select_peca = False

    if st.session_state.proximo_select_peca:
        st.session_state.select_codigo = st.session_state.proximo_select_peca
        st.session_state.codigo_selecionado = st.session_state.proximo_select_peca
        st.session_state.proximo_select_peca = ""

    if st.session_state.select_codigo and st.session_state.select_codigo not in lista_codigos:
        st.session_state.select_codigo = ""
        st.session_state.codigo_selecionado = ""

    indice_atual = lista_codigos.index(st.session_state.select_codigo) if st.session_state.select_codigo in lista_codigos else 0

    bloqueia_menu = st.session_state.acao in ["novo", "editar"]
    tem_peca_selecionada = bool(st.session_state.select_codigo)

    selecionado = st.selectbox(
        "Selecione uma peça cadastrada",
        options=lista_codigos,
        index=indice_atual,
        format_func=lambda codigo: opcoes_select[codigo],
        key="select_codigo",
        help="Use a seleção para editar ou excluir uma peça já cadastrada.",
        disabled=bloqueia_menu
    )

    if st.session_state.acao != "editar":
        st.session_state.codigo_selecionado = selecionado

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Novo", key="btn_novo_peca", type="primary", disabled=bloqueia_menu, use_container_width=True):
            st.session_state.acao = "novo"
            st.rerun()

    with col2:
        if st.button("Editar", key="btn_editar_peca", type="primary", disabled=bloqueia_menu or not tem_peca_selecionada, use_container_width=True):
            st.session_state.acao = "editar"
            st.session_state.codigo_selecionado = st.session_state.select_codigo
            st.rerun()

    with col3:
        if st.button("Excluir", key="btn_excluir_peca", type="primary", disabled=bloqueia_menu or not tem_peca_selecionada, use_container_width=True):
            st.session_state.acao = "excluir"
            st.session_state.codigo_selecionado = st.session_state.select_codigo
            st.rerun()

    with col4:
        if st.button("Cancelar", key="btn_cancelar_peca", type="primary", use_container_width=True):
            limpar_modo()

    st.divider()

    if st.session_state.acao == "novo":
        tela_nova_peca(lista_pecas)
    elif st.session_state.acao == "editar":
        tela_editar_peca()
    elif st.session_state.acao == "excluir":
        tela_excluir_peca()
    else:
        exibir_tabela_pecas(lista_pecas)


# ==========================================================
# MENU PRINCIPAL
# ==========================================================

def menu_peca():
    st.set_page_config(page_title="Cadastro de peças", layout="wide")
    aplicar_estilo_pecas()
    inicializar_estado()

    lista_pecas = repo.listar()

    st.markdown(
        """
        <h1 style="
            text-align:left;
            color:black;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 34px;
            font-weight: 700;
            margin-bottom: 0.45rem;
            letter-spacing: 0.3px;
        ">
            CADASTRO DE PEÇAS
        </h1>
        """,
        unsafe_allow_html=True
    )

    tela_cadastro(lista_pecas)


if __name__ == "__main__":
    menu_peca()