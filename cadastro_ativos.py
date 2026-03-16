import io
import pandas as pd
import streamlit as st
from database import SupabaseAssetRepository, SupabasePartRepository, SupabasePhotoStorage


# ==========================================================
# REPOSITÓRIOS / STORAGE
# ==========================================================
asset_repo = SupabaseAssetRepository()
part_repo = SupabasePartRepository()
photo_storage = SupabasePhotoStorage()


# ==========================================================
# ESTILO GLOBAL
# ==========================================================

def aplicar_estilo_cadastro():
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

        /* BOTÕES PADRÃO DA TELA */
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

        /* APENAS BOTÕES PRIMARY = LARANJA */
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

        /* DESABILITADO MAIS FRACO */
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

        div[data-testid="stFileUploader"] section {
            border: 2px dashed #c97a00 !important;
            border-radius: 12px !important;
            background: #fffdf7 !important;
        }

        .bloco-arquivos {
            border: 1px solid rgba(127,127,127,0.18);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            background: #ffffff;
            margin-bottom: 1rem;
        }

        .bloco-arquivos h4 {
            margin: 0 0 0.65rem 0;
            font-family: Consolas, "Courier New", monospace !important;
            font-size: 18px !important;
            font-weight: 700 !important;
            color: #000000 !important;
        }

        .arquivo-linha {
            border: 1px solid rgba(127,127,127,0.14);
            border-radius: 12px;
            padding: 0.6rem 0.75rem;
            margin-bottom: 0.55rem;
            background: #fffdf7;
        }

        .caption-arquivo {
            font-family: Consolas, "Courier New", monospace !important;
            font-weight: 700 !important;
            color: #000000 !important;
            word-break: break-word;
        }

        .arquivo-preview-gap {
            margin-top: 0.45rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# ==========================================================
# UTILITÁRIOS
# ==========================================================

def normalizar_texto(valor):
    return str(valor or "").strip().upper()


@st.cache_data(ttl=10, show_spinner=False)
def carregar_ativos_cache():
    return asset_repo.list_assets()


@st.cache_data(ttl=120, show_spinner=False)
def ler_bytes_storage_cache(storage_key):
    if not storage_key:
        return None
    try:
        return photo_storage.get_bytes({"storage_key": storage_key})
    except Exception:
        return None


def limpar_caches():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def inicializar_estado():
    padrao = {
        "acao_ativo": "",
        "ativo_select": "",
        "ativo_tag_selecionado": "",
        "pecas_vinculadas": [],
        "resetar_ativo_select": False,
        "proximo_ativo_select": "",
        "filtro_tipo_lista_ativos": "Todos",
        "filtro_busca_lista_ativos": "",
        "fotos_editando": [],
        "pdfs_editando": [],
        "arquivos_form_inicializados": False,
    }

    for chave, valor in padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def limpar_estado(limpar_selecao=False):
    st.session_state.acao_ativo = ""
    st.session_state.pecas_vinculadas = []
    st.session_state.fotos_editando = []
    st.session_state.pdfs_editando = []
    st.session_state.arquivos_form_inicializados = False

    if limpar_selecao:
        st.session_state.resetar_ativo_select = True
        st.session_state.ativo_tag_selecionado = ""

    st.rerun()


def buscar_ativo_por_tag(lista_ativos, tag):
    tag = normalizar_texto(tag)
    return next(
        (a for a in lista_ativos if normalizar_texto(a.get("tag")) == tag),
        None
    )


def tag_ja_existe(lista_ativos, tag, ignorar_tag=None):
    tag = normalizar_texto(tag)
    ignorar_tag = normalizar_texto(ignorar_tag)

    for ativo in lista_ativos:
        tag_existente = normalizar_texto(ativo.get("tag"))
        if ignorar_tag and tag_existente == ignorar_tag:
            continue
        if tag_existente == tag:
            return True
    return False


def montar_select_ativos(lista_ativos):
    opcoes = {"": ""}
    for ativo in lista_ativos:
        tag = ativo.get("tag", "")
        descricao = ativo.get("descricao", "")
        tipo = ativo.get("tipo", "")
        if tag:
            opcoes[tag] = f"{tag} - {descricao} [{tipo}]" if descricao else f"{tag} [{tipo}]"
    return opcoes


def nome_arquivo_item(item):
    if isinstance(item, dict):
        return (
            item.get("nome_original")
            or item.get("nome")
            or item.get("filename")
            or item.get("arquivo")
            or "ARQUIVO"
        )
    return str(item or "ARQUIVO")


def resetar_estado_formulario_arquivos():
    st.session_state.fotos_editando = []
    st.session_state.pdfs_editando = []
    st.session_state.arquivos_form_inicializados = False


# ==========================================================
# REGRAS DE NEGÓCIO / HIERARQUIA
# ==========================================================

def ativo_e_local_principal(ativo):
    return bool(ativo.get("local_principal", False))


def obter_local_principal_existente(lista_ativos, ignorar_tag=None):
    ignorar_tag = normalizar_texto(ignorar_tag)

    for ativo in lista_ativos:
        tag = normalizar_texto(ativo.get("tag"))
        if ignorar_tag and tag == ignorar_tag:
            continue
        if ativo_e_local_principal(ativo):
            return ativo
    return None


def existe_local_principal(lista_ativos, ignorar_tag=None):
    return obter_local_principal_existente(lista_ativos, ignorar_tag=ignorar_tag) is not None


def listar_pais_validos(lista_ativos, tipo, tag_atual=None):
    opcoes = [""]
    tag_atual = normalizar_texto(tag_atual)

    for ativo in lista_ativos:
        tag = normalizar_texto(ativo.get("tag"))
        tipo_ativo = ativo.get("tipo", "")

        if not tag or tag == tag_atual:
            continue

        if tipo == "Local" and tipo_ativo == "Local":
            opcoes.append(tag)
        elif tipo == "Equipamento" and tipo_ativo == "Local":
            opcoes.append(tag)
        elif tipo == "Componente" and tipo_ativo == "Equipamento":
            opcoes.append(tag)

    return opcoes


def validar_hierarquia(dados, lista_ativos, tag_original=None):
    tipo = dados["tipo"]
    pai = normalizar_texto(dados["pai"])

    if tipo == "Local":
        if dados["local_principal"]:
            if pai:
                return "Local Principal não pode ter pai."
            if existe_local_principal(lista_ativos, ignorar_tag=tag_original):
                return "Já existe um Local Principal cadastrado. Só pode haver um."
        elif pai:
            ativo_pai = buscar_ativo_por_tag(lista_ativos, pai)
            if not ativo_pai or ativo_pai.get("tipo") != "Local":
                return "O pai de um Local deve ser outro Local."

    elif tipo == "Equipamento":
        if not pai:
            return "Todo equipamento deve ter um pai do tipo Local."
        ativo_pai = buscar_ativo_por_tag(lista_ativos, pai)
        if not ativo_pai or ativo_pai.get("tipo") != "Local":
            return "O pai do Equipamento deve ser um ativo do tipo Local."

    elif tipo == "Componente":
        if not pai:
            return "Todo componente deve ter um pai do tipo Equipamento."
        ativo_pai = buscar_ativo_por_tag(lista_ativos, pai)
        if not ativo_pai or ativo_pai.get("tipo") != "Equipamento":
            return "O pai do Componente deve ser um ativo do tipo Equipamento."

    return ""


def validar_dados(dados, lista_ativos, tag_original=None):
    if not dados["tag"]:
        return "A TAG é obrigatória."

    if dados["tipo"] == "Componente" and not dados["tag_local"]:
        return "Informe a TAG do componente."

    if tag_ja_existe(lista_ativos, dados["tag"], ignorar_tag=tag_original):
        return "Esta TAG já existe e não pode ser repetida."

    erro = validar_hierarquia(dados, lista_ativos, tag_original)
    if erro:
        return erro

    return ""


# ==========================================================
# PEÇAS
# ==========================================================

def montar_texto_peca(peca):
    codigo = str(peca.get("codigo", "")).strip()
    descricao = str(peca.get("descricao", "")).strip()

    if codigo and descricao:
        return f"{codigo} - {descricao}"
    return codigo or descricao


def mostrar_vinculo_pecas(pecas_iniciais=None):
    lista_pecas = part_repo.list_parts()

    if pecas_iniciais is not None and not st.session_state.pecas_vinculadas:
        st.session_state.pecas_vinculadas = [dict(p) for p in pecas_iniciais]

    st.subheader("Peças do componente")

    if not lista_pecas:
        st.info("Nenhuma peça cadastrada.")
        return st.session_state.pecas_vinculadas

    mapa_pecas = {}
    for peca in lista_pecas:
        codigo = peca.get("codigo")
        if codigo:
            mapa_pecas[codigo] = {
                "codigo": codigo,
                "referencia": peca.get("referencia", ""),
                "descricao": peca.get("descricao", ""),
                "texto": montar_texto_peca(peca),
            }

    codigos = [""] + list(mapa_pecas.keys())

    col_funcao, col_peca, col_qtd = st.columns([4, 5, 1])

    with col_funcao:
        funcao_peca = st.text_input(
            "Função da peça",
            key="peca_funcao",
            placeholder="Ex.: GAXETA ÊMBOLO"
        )

    with col_peca:
        codigo_peca = st.selectbox(
            "Peça",
            options=codigos,
            format_func=lambda c: "" if c == "" else mapa_pecas[c]["texto"],
            key="peca_codigo"
        )

    with col_qtd:
        quantidade = st.number_input(
            "Qtd",
            min_value=1,
            step=1,
            value=1,
            key="peca_quantidade"
        )

    if st.button("Adicionar peça", key="btn_adicionar_peca", use_container_width=True):
        if not codigo_peca:
            st.error("Selecione uma peça.")
        else:
            dados_peca = mapa_pecas[codigo_peca]
            funcao_normalizada = normalizar_texto(funcao_peca)

            existente = next(
                (
                    p for p in st.session_state.pecas_vinculadas
                    if p["codigo"] == codigo_peca and normalizar_texto(p.get("funcao", "")) == funcao_normalizada
                ),
                None
            )

            if existente:
                existente["quantidade"] += quantidade
            else:
                st.session_state.pecas_vinculadas.append({
                    "funcao": funcao_normalizada,
                    "referencia": dados_peca["referencia"],
                    "codigo": dados_peca["codigo"],
                    "descricao": dados_peca["descricao"],
                    "quantidade": quantidade,
                })

            limpar_caches()
            st.rerun()

    if st.session_state.pecas_vinculadas:
        st.markdown("### Peças adicionadas")

        for i, item in enumerate(st.session_state.pecas_vinculadas):
            c1, c2, c3, c4 = st.columns([3, 5, 2, 1])

            with c1:
                st.write(normalizar_texto(item.get("funcao", "")) or "-")

            with c2:
                st.write(montar_texto_peca(item))

            with c3:
                st.write(f'Qtd: {item["quantidade"]}')

            with c4:
                if st.button("Remover", key=f"remover_peca_{i}", use_container_width=True):
                    st.session_state.pecas_vinculadas.pop(i)
                    st.rerun()

    return st.session_state.pecas_vinculadas


# ==========================================================
# ARQUIVOS
# ==========================================================

def remover_item_em_edicao(tipo_lista, indice):
    if tipo_lista == "foto":
        if 0 <= indice < len(st.session_state.fotos_editando):
            st.session_state.fotos_editando.pop(indice)
    elif tipo_lista == "pdf":
        if 0 <= indice < len(st.session_state.pdfs_editando):
            st.session_state.pdfs_editando.pop(indice)

    st.rerun()


def mostrar_item_arquivo_editavel(item, prefixo, indice, mostrar_preview=False):
    nome = nome_arquivo_item(item)

    st.markdown("<div class='arquivo-linha'>", unsafe_allow_html=True)
    col_x, col_nome = st.columns([1, 12])

    with col_x:
        if st.button("✕", key=f"{prefixo}_remover_{indice}", use_container_width=True):
            remover_item_em_edicao(prefixo, indice)

    with col_nome:
        st.markdown(f"<div class='caption-arquivo'>{nome}</div>", unsafe_allow_html=True)

        if mostrar_preview:
            conteudo = ler_bytes_storage_cache(item.get("storage_key", ""))
            if conteudo:
                st.markdown("<div class='arquivo-preview-gap'>", unsafe_allow_html=True)
                st.image(conteudo, width=180)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("Arquivo não encontrado.")

    st.markdown("</div>", unsafe_allow_html=True)


def mostrar_bloco_arquivos(fotos_atuais=None, pdfs_atuais=None):
    fotos_atuais = fotos_atuais or []
    pdfs_atuais = pdfs_atuais or []

    if not st.session_state.arquivos_form_inicializados:
        st.session_state.fotos_editando = list(fotos_atuais)
        st.session_state.pdfs_editando = list(pdfs_atuais)
        st.session_state.arquivos_form_inicializados = True

    st.subheader("Anexos")

    st.markdown("<div class='bloco-arquivos'><h4>IMAGENS</h4></div>", unsafe_allow_html=True)
    if st.session_state.fotos_editando:
        for i, foto in enumerate(st.session_state.fotos_editando):
            mostrar_item_arquivo_editavel(
                foto,
                prefixo="foto",
                indice=i,
                mostrar_preview=True
            )
    else:
        st.info("Nenhuma imagem cadastrada.")

    origem_imagem = st.radio(
        "Adicionar imagem por",
        options=["Arquivos", "Câmera"],
        horizontal=True,
        key="form_origem_imagem"
    )

    novas_fotos = []

    if origem_imagem == "Câmera":
        foto_camera = st.camera_input(
            "Tirar foto com a câmera",
            key="form_foto_camera"
        )
        if foto_camera is not None:
            novas_fotos.append(foto_camera)
    else:
        novas_fotos_upload = st.file_uploader(
            "Anexar imagens",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="form_fotos"
        )
        if novas_fotos_upload:
            novas_fotos.extend(list(novas_fotos_upload))

    st.markdown("<div class='bloco-arquivos'><h4>PDFS</h4></div>", unsafe_allow_html=True)
    if st.session_state.pdfs_editando:
        for i, pdf in enumerate(st.session_state.pdfs_editando):
            mostrar_item_arquivo_editavel(
                pdf,
                prefixo="pdf",
                indice=i,
                mostrar_preview=False
            )
    else:
        st.info("Nenhum PDF cadastrado.")

    novos_pdfs = st.file_uploader(
        "Anexar PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key="form_pdfs"
    )

    return st.session_state.fotos_editando, novas_fotos, st.session_state.pdfs_editando, novos_pdfs


# ==========================================================
# FORMULÁRIO
# ==========================================================

def construir_formulario(lista_ativos, ativo_edicao=None):
    editando = ativo_edicao is not None

    tipo_inicial = ativo_edicao.get("tipo", "Local") if editando else "Local"
    tag_inicial = ativo_edicao.get("tag", "") if editando else ""
    tag_local_inicial = ativo_edicao.get("tag_local", "") if editando else ""
    descricao_inicial = ativo_edicao.get("descricao", "") if editando else ""
    observacoes_inicial = ativo_edicao.get("observacoes", "") if editando else ""
    fabricante_inicial = ativo_edicao.get("fabricante", "") if editando else ""
    modelo_inicial = ativo_edicao.get("modelo", "") if editando else ""
    pai_inicial = ativo_edicao.get("pai", "") if editando else ""
    fotos_atuais = ativo_edicao.get("fotos", []) if editando else []
    pdfs_atuais = ativo_edicao.get("pdfs", []) if editando else []

    tipo = st.selectbox(
        "Tipo do ativo",
        ["Local", "Equipamento", "Componente"],
        index=["Local", "Equipamento", "Componente"].index(tipo_inicial),
        key="form_tipo"
    )

    local_principal = False
    if tipo == "Local":
        tag_referencia = tag_inicial if editando else ""
        principal_existente = obter_local_principal_existente(lista_ativos, ignorar_tag=tag_referencia)
        pode_marcar_principal = principal_existente is None

        if principal_existente:
            st.info(
                f"Já existe um Local Principal cadastrado: {principal_existente.get('tag', '')} - {principal_existente.get('descricao', '')}"
            )

        local_principal = st.toggle(
            "Local Principal",
            value=bool(ativo_edicao.get("local_principal", False)) if editando else False,
            key="form_local_principal",
            disabled=not pode_marcar_principal,
            help=None if pode_marcar_principal else "Já existe um Local Principal cadastrado."
        )

    descricao = ""
    pai = ""
    tag_local = ""
    tag_final = tag_inicial if editando else ""

    col_tag, col_desc = st.columns([5, 15])

    if tipo == "Componente":
        with col_tag:
            tag_local = st.text_input(
                "TAG do componente",
                value=tag_local_inicial,
                key="form_tag_local"
            )

        with col_desc:
            descricao = st.text_input(
                "Descrição",
                value=descricao_inicial,
                key="form_descricao"
            )

        opcoes_pai = listar_pais_validos(lista_ativos, tipo, tag_inicial if editando else None)
        indice_pai = opcoes_pai.index(pai_inicial) if pai_inicial in opcoes_pai else 0

        pai = st.selectbox(
            "Equipamento pai",
            options=opcoes_pai,
            index=indice_pai,
            format_func=lambda tag: tag if tag else "Selecione",
            key="form_pai_componente"
        )

        tag_local_normalizada = normalizar_texto(tag_local)
        pai_normalizado = normalizar_texto(pai)

        if tag_local_normalizada and pai_normalizado:
            tag_final = f"{tag_local_normalizada} [{pai_normalizado}]"
        else:
            tag_final = ""

        st.info(
            f"TAG final: {tag_final if tag_final else 'Preencha a TAG do componente e o equipamento pai'}"
        )

    else:
        with col_tag:
            tag_final = st.text_input("TAG", value=tag_inicial, key="form_tag")

        with col_desc:
            descricao = st.text_input("Descrição", value=descricao_inicial, key="form_descricao")

    observacoes = st.text_area("Observações", value=observacoes_inicial, key="form_observacoes")

    fabricante = ""
    modelo = ""
    if tipo in ["Equipamento", "Componente"]:
        col_fabricante, col_modelo = st.columns(2)

        with col_fabricante:
            fabricante = st.text_input("Fabricante", value=fabricante_inicial, key="form_fabricante")

        with col_modelo:
            modelo = st.text_input("Modelo", value=modelo_inicial, key="form_modelo")

    if tipo == "Local":
        if local_principal:
            pai = ""
        else:
            opcoes_pai = listar_pais_validos(lista_ativos, tipo, tag_inicial if editando else None)
            indice_pai = opcoes_pai.index(pai_inicial) if pai_inicial in opcoes_pai else 0

            pai = st.selectbox(
                "Local pai",
                options=opcoes_pai,
                index=indice_pai,
                format_func=lambda tag: tag if tag else "Selecione",
                key="form_pai_local"
            )

    elif tipo == "Equipamento":
        opcoes_pai = listar_pais_validos(lista_ativos, tipo, tag_inicial if editando else None)
        indice_pai = opcoes_pai.index(pai_inicial) if pai_inicial in opcoes_pai else 0

        pai = st.selectbox(
            "Local pai",
            options=opcoes_pai,
            index=indice_pai,
            format_func=lambda tag: tag if tag else "Selecione",
            key="form_pai_equipamento"
        )

    fotos_mantidas, novas_fotos, pdfs_mantidos, novos_pdfs = mostrar_bloco_arquivos(
        fotos_atuais,
        pdfs_atuais
    )

    pecas = []
    if tipo == "Componente":
        st.divider()
        pecas = mostrar_vinculo_pecas(ativo_edicao.get("pecas", []) if editando else [])

    return {
        "tipo": tipo,
        "local_principal": local_principal,
        "tag": f"{normalizar_texto(tag_local)} [{normalizar_texto(pai)}]" if tipo == "Componente" and normalizar_texto(tag_local) and normalizar_texto(pai) else normalizar_texto(tag_final),
        "tag_local": normalizar_texto(tag_local),
        "descricao": normalizar_texto(descricao),
        "observacoes": observacoes.strip(),
        "fabricante": normalizar_texto(fabricante),
        "modelo": normalizar_texto(modelo),
        "pai": normalizar_texto(pai),
        "fotos_mantidas": fotos_mantidas,
        "novas_fotos": novas_fotos,
        "pdfs_mantidos": pdfs_mantidos,
        "novos_pdfs": novos_pdfs,
        "pecas": pecas,
    }


# ==========================================================
# PERSISTÊNCIA
# ==========================================================

def montar_registro_ativo(dados, fotos_salvas, pdfs_salvos):
    return {
        "tipo": dados["tipo"],
        "local_principal": dados["local_principal"],
        "tag": dados["tag"],
        "tag_local": dados["tag_local"],
        "descricao": dados["descricao"],
        "observacoes": dados["observacoes"],
        "fabricante": dados["fabricante"],
        "modelo": dados["modelo"],
        "pai": dados["pai"],
        "fotos": fotos_salvas,
        "pdfs": pdfs_salvos,
        "pecas": dados["pecas"] if dados["tipo"] == "Componente" else [],
    }


# ==========================================================
# EXPORTAÇÃO / LISTA
# ==========================================================

def montar_dataframe_ativos(lista_ativos):
    registros = []

    for ativo in lista_ativos:
        fotos = ativo.get("fotos", []) or []
        pdfs = ativo.get("pdfs", []) or []
        pecas = ativo.get("pecas", []) or []

        classificacao = "Local Principal" if ativo_e_local_principal(ativo) else ""

        pecas_texto = " | ".join(
            [
                f'{normalizar_texto(p.get("funcao", "")) or "-"} | {p.get("codigo", "")} - {p.get("descricao", "")} | Qtd: {p.get("quantidade", 0)}'
                for p in pecas
            ]
        )

        registros.append({
            "TAG": ativo.get("tag", ""),
            "TIPO": ativo.get("tipo", ""),
            "TAG_COMPONENTE": ativo.get("tag_local", ""),
            "DESCRICAO": ativo.get("descricao", ""),
            "CLASSIFICACAO": classificacao,
            "PAI": ativo.get("pai", ""),
            "FABRICANTE": ativo.get("fabricante", ""),
            "MODELO": ativo.get("modelo", ""),
            "OBSERVACOES": ativo.get("observacoes", ""),
            "QTD_FOTOS": len(fotos),
            "QTD_PDFS": len(pdfs),
            "QTD_PECAS": len(pecas),
            "PECAS": pecas_texto,
        })

    df = pd.DataFrame(registros)

    if not df.empty:
        df = df.sort_values(by=["TIPO", "TAG"], ascending=[True, True]).reset_index(drop=True)

    return df


def gerar_xlsx_ativos(df):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ativos")

        ws = writer.sheets["Ativos"]

        larguras = {
            "A": 22,
            "B": 16,
            "C": 22,
            "D": 30,
            "E": 20,
            "F": 22,
            "G": 20,
            "H": 20,
            "I": 40,
            "J": 12,
            "K": 12,
            "L": 12,
            "M": 80,
        }

        for coluna, largura in larguras.items():
            ws.column_dimensions[coluna].width = largura

    output.seek(0)
    return output.getvalue()


def mostrar_lista_ativos(lista_ativos):
    st.subheader("Lista de ativos")

    if not lista_ativos:
        st.info("Nenhum ativo cadastrado.")
        return

    df = montar_dataframe_ativos(lista_ativos)

    col_filtro_tipo, col_filtro_busca = st.columns([1, 2])

    with col_filtro_tipo:
        tipo_filtro = st.selectbox(
            "Filtrar por tipo",
            options=["Todos", "Local", "Equipamento", "Componente"],
            key="filtro_tipo_lista_ativos"
        )

    with col_filtro_busca:
        busca = st.text_input(
            "Buscar por TAG, descrição, pai, fabricante ou modelo",
            key="filtro_busca_lista_ativos",
            placeholder="Digite para filtrar a lista"
        ).strip().upper()

    df_filtrado = df.copy()

    if tipo_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["TIPO"] == tipo_filtro]

    if busca:
        mascara = (
            df_filtrado["TAG"].fillna("").astype(str).str.upper().str.contains(busca, na=False) |
            df_filtrado["DESCRICAO"].fillna("").astype(str).str.upper().str.contains(busca, na=False) |
            df_filtrado["PAI"].fillna("").astype(str).str.upper().str.contains(busca, na=False) |
            df_filtrado["FABRICANTE"].fillna("").astype(str).str.upper().str.contains(busca, na=False) |
            df_filtrado["MODELO"].fillna("").astype(str).str.upper().str.contains(busca, na=False)
        )
        df_filtrado = df_filtrado[mascara]

    st.caption(f"{len(df_filtrado)} ativo(s) encontrado(s).")

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        hide_index=True
    )

    xlsx_bytes = gerar_xlsx_ativos(df_filtrado)

    st.download_button(
        "📗 Exportar lista em XLSX",
        data=xlsx_bytes,
        file_name="ativos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


# ==========================================================
# TELAS DE AÇÃO
# ==========================================================

def tela_novo_ativo(lista_ativos):
    st.subheader("Novo ativo")

    dados = construir_formulario(lista_ativos)

    if st.button("Salvar", key="btn_salvar_novo", use_container_width=True):
        erro = validar_dados(dados, lista_ativos)

        if erro:
            st.error(erro)
            return

        novas_fotos_salvas = photo_storage.save_uploaded_files(dados["novas_fotos"], dados["tag"])
        novos_pdfs_salvos = photo_storage.save_uploaded_files(dados["novos_pdfs"], dados["tag"])

        fotos_finais = dados["fotos_mantidas"] + novas_fotos_salvas
        pdfs_finais = dados["pdfs_mantidos"] + novos_pdfs_salvos

        asset_repo.create_asset(montar_registro_ativo(dados, fotos_finais, pdfs_finais))
        limpar_caches()

        st.session_state.acao_ativo = ""
        st.session_state.ativo_tag_selecionado = ""
        st.session_state.pecas_vinculadas = []
        st.session_state.resetar_ativo_select = True
        resetar_estado_formulario_arquivos()
        st.rerun()


def tela_editar_ativo(lista_ativos):
    st.subheader("Editar ativo")

    tag = st.session_state.ativo_tag_selecionado
    ativo = asset_repo.get_asset_by_tag(tag) if tag else None

    if not tag:
        st.error("Selecione um ativo para editar.")
        return

    if not ativo:
        st.error("Ativo não encontrado.")
        return

    # NÃO alterar st.session_state.ativo_select aqui.
    # O selectbox já foi renderizado nesta execução.
    # Mantemos apenas a referência interna do ativo em edição.
    st.session_state.ativo_tag_selecionado = ativo["tag"]

    dados = construir_formulario(lista_ativos, ativo_edicao=ativo)

    if st.button("Salvar edição", key="btn_salvar_edicao", use_container_width=True):
        erro = validar_dados(dados, lista_ativos, tag_original=ativo["tag"])

        if erro:
            st.error(erro)
            return

        fotos_anteriores = ativo.get("fotos", []) or []
        pdfs_anteriores = ativo.get("pdfs", []) or []

        fotos_mantidas = dados["fotos_mantidas"]
        pdfs_mantidos = dados["pdfs_mantidos"]

        fotos_removidas = [f for f in fotos_anteriores if f not in fotos_mantidas]
        pdfs_removidos = [p for p in pdfs_anteriores if p not in pdfs_mantidos]

        if fotos_removidas:
            photo_storage.delete_many(fotos_removidas)

        if pdfs_removidos:
            photo_storage.delete_many(pdfs_removidos)

        novas_fotos_salvas = photo_storage.save_uploaded_files(dados["novas_fotos"], dados["tag"])
        novos_pdfs_salvos = photo_storage.save_uploaded_files(dados["novos_pdfs"], dados["tag"])

        fotos_finais = fotos_mantidas + novas_fotos_salvas
        pdfs_finais = pdfs_mantidos + novos_pdfs_salvos

        asset_repo.update_asset(
            ativo["tag"],
            montar_registro_ativo(dados, fotos_finais, pdfs_finais)
        )
        limpar_caches()

        st.session_state.acao_ativo = ""
        st.session_state.ativo_tag_selecionado = dados["tag"]
        st.session_state.pecas_vinculadas = []
        st.session_state.proximo_ativo_select = dados["tag"]
        resetar_estado_formulario_arquivos()
        st.rerun()


def tela_excluir_ativo():
    st.subheader("Excluir ativo")

    tag = st.session_state.ativo_tag_selecionado
    ativo = asset_repo.get_asset_by_tag(tag) if tag else None

    if not tag:
        st.error("Selecione um ativo para excluir.")
        return

    if not ativo:
        st.error("Ativo não encontrado.")
        return

    st.warning(f'Confirma a exclusão de {ativo["tag"]} - {ativo.get("descricao", "")}?')

    if st.button("Confirmar exclusão", key="btn_confirmar_exclusao", use_container_width=True):
        fotos = ativo.get("fotos", []) or []
        pdfs = ativo.get("pdfs", []) or []

        if fotos:
            photo_storage.delete_many(fotos)

        if pdfs:
            photo_storage.delete_many(pdfs)

        asset_repo.delete_asset(tag)
        limpar_caches()

        st.session_state.acao_ativo = ""
        st.session_state.ativo_tag_selecionado = ""
        st.session_state.pecas_vinculadas = []
        st.session_state.resetar_ativo_select = True
        resetar_estado_formulario_arquivos()
        st.rerun()


# ==========================================================
# TELA PRINCIPAL
# ==========================================================

def mostrar_cadastro():
    aplicar_estilo_cadastro()
    inicializar_estado()
    lista_ativos = carregar_ativos_cache()

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
            CADASTRO DE ATIVOS
        </h1>
        """,
        unsafe_allow_html=True
    )

    # Essas alterações acontecem ANTES do selectbox ser criado.
    if st.session_state.resetar_ativo_select:
        st.session_state.ativo_select = ""
        st.session_state.ativo_tag_selecionado = ""
        st.session_state.resetar_ativo_select = False

    if st.session_state.proximo_ativo_select:
        st.session_state.ativo_select = st.session_state.proximo_ativo_select
        st.session_state.ativo_tag_selecionado = st.session_state.proximo_ativo_select
        st.session_state.proximo_ativo_select = ""

    opcoes_select = montar_select_ativos(lista_ativos)
    lista_tags = list(opcoes_select.keys())

    if st.session_state.ativo_select and st.session_state.ativo_select not in lista_tags:
        st.session_state.ativo_select = ""
        st.session_state.ativo_tag_selecionado = ""

    indice_atual = lista_tags.index(st.session_state.ativo_select) if st.session_state.ativo_select in lista_tags else 0

    bloqueia_menu = st.session_state.acao_ativo in ["novo", "editar"]
    tem_ativo_selecionado = bool(st.session_state.ativo_select)

    selecionado = st.selectbox(
        "Selecione um ativo cadastrado",
        options=lista_tags,
        index=indice_atual,
        format_func=lambda tag: opcoes_select[tag],
        key="ativo_select",
        help="Use a seleção para editar ou excluir um ativo já cadastrado.",
        disabled=bloqueia_menu
    )

    if st.session_state.acao_ativo == "editar":
        # Durante a edição, mantém o item interno fixo.
        # Não mexemos mais em ativo_select aqui.
        pass
    else:
        st.session_state.ativo_tag_selecionado = selecionado

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Novo", key="btn_novo_topo", type="primary", disabled=bloqueia_menu, use_container_width=True):
            st.session_state.acao_ativo = "novo"
            st.session_state.pecas_vinculadas = []
            resetar_estado_formulario_arquivos()
            st.rerun()

    with col2:
        if st.button("Editar", key="btn_editar_topo", type="primary", disabled=bloqueia_menu or not tem_ativo_selecionado, use_container_width=True):
            st.session_state.acao_ativo = "editar"
            st.session_state.ativo_tag_selecionado = st.session_state.ativo_select
            st.session_state.pecas_vinculadas = []
            resetar_estado_formulario_arquivos()
            st.rerun()

    with col3:
        if st.button("Excluir", key="btn_excluir_topo", type="primary", disabled=bloqueia_menu or not tem_ativo_selecionado, use_container_width=True):
            st.session_state.acao_ativo = "excluir"
            st.session_state.ativo_tag_selecionado = st.session_state.ativo_select
            resetar_estado_formulario_arquivos()
            st.rerun()

    with col4:
        if st.button("Cancelar", key="btn_cancelar_topo", type="primary", use_container_width=True):
            limpar_estado()

    st.divider()

    if st.session_state.acao_ativo == "novo":
        tela_novo_ativo(lista_ativos)
    elif st.session_state.acao_ativo == "editar":
        tela_editar_ativo(lista_ativos)
    elif st.session_state.acao_ativo == "excluir":
        tela_excluir_ativo()
    else:
        mostrar_lista_ativos(lista_ativos)