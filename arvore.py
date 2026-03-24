import html
import json
import base64
import mimetypes
import re

import streamlit as st
import streamlit.components.v1 as components
from st_keyup import st_keyup

from database import SupabaseAssetRepository, SupabasePhotoStorage


# ============================================================
# CONFIGURAÇÃO BÁSICA
# ============================================================
asset_repo = SupabaseAssetRepository()
photo_storage = SupabasePhotoStorage()


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================
def normalizar_texto(valor):
    return str(valor or "").strip().upper()


def detectar_mime(nome_arquivo):
    nome = str(nome_arquivo or "").lower()

    if nome.endswith(".png"):
        return "image/png"
    if nome.endswith(".jpg") or nome.endswith(".jpeg"):
        return "image/jpeg"
    if nome.endswith(".webp"):
        return "image/webp"
    if nome.endswith(".gif"):
        return "image/gif"
    if nome.endswith(".pdf"):
        return "application/pdf"

    mime, _ = mimetypes.guess_type(nome)
    return mime or "application/octet-stream"


def eh_imagem(nome_arquivo):
    return detectar_mime(nome_arquivo).startswith("image/")


def eh_pdf(nome_arquivo):
    return detectar_mime(nome_arquivo) == "application/pdf"


def bytes_para_data_url(nome_arquivo, conteudo):
    mime = detectar_mime(nome_arquivo)
    b64 = base64.b64encode(conteudo).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def nome_item_anexo(item, nome_padrao="ARQUIVO"):
    return (
        item.get("nome_original")
        or item.get("nome")
        or item.get("filename")
        or item.get("arquivo")
        or nome_padrao
    )


def destacar_termo_html(texto, termo):
    texto = str(texto or "")
    termo = str(termo or "").strip()

    if not termo:
        return html.escape(texto)

    partes = re.split(f"({re.escape(termo)})", texto, flags=re.IGNORECASE)

    saida = []
    for parte in partes:
        if not parte:
            continue

        if parte.lower() == termo.lower():
            saida.append(f"<mark class='highlight-mark'>{html.escape(parte)}</mark>")
        else:
            saida.append(html.escape(parte))

    return "".join(saida)


def extrair_pai_da_tag_componente(tag):
    tag = str(tag or "").strip()
    m = re.search(r"\[([^\[\]]+)\]\s*$", tag)
    if m:
        return normalizar_texto(m.group(1))
    return ""


def obter_pai_relacional(ativo):
    pai = normalizar_texto(ativo.get("pai", ""))
    if pai:
        return pai

    tipo = normalizar_texto(ativo.get("tipo", ""))
    tag = normalizar_texto(ativo.get("tag", ""))

    if tipo == "COMPONENTE":
        pai_extraido = extrair_pai_da_tag_componente(tag)
        if pai_extraido:
            return pai_extraido

    return ""


def chave_ativo(ativo):
    tag = normalizar_texto(ativo.get("tag", ""))
    return tag or f"SEM_TAG_{id(ativo)}"


# ============================================================
# CACHE DE DADOS
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def carregar_ativos_cache():
    return asset_repo.list_assets()


@st.cache_data(ttl=600, show_spinner=False)
def ler_bytes_storage_cache(storage_key):
    if not storage_key:
        return None
    try:
        return photo_storage.get_bytes({"storage_key": storage_key})
    except Exception:
        return None


def carregar_ativos():
    return carregar_ativos_cache()


# ============================================================
# DADOS DOS ATIVOS
# ============================================================
def montar_mapa_filhos(lista):
    mapa = {}

    for ativo in lista:
        pai = obter_pai_relacional(ativo)
        mapa.setdefault(pai, []).append(ativo)

    return mapa


def montar_raizes(lista):
    tags_existentes = {
        normalizar_texto(ativo.get("tag", ""))
        for ativo in lista
        if normalizar_texto(ativo.get("tag", ""))
    }

    raizes = []

    for ativo in lista:
        pai = obter_pai_relacional(ativo)

        if not pai:
            raizes.append(ativo)
            continue

        if pai not in tags_existentes:
            raizes.append(ativo)

    return raizes


@st.cache_data(ttl=300, show_spinner=False)
def carregar_estrutura_cache():
    lista = asset_repo.list_assets()
    mapa_filhos = montar_mapa_filhos(lista)
    raizes = montar_raizes(lista)
    return lista, mapa_filhos, raizes


# ============================================================
# PEÇAS
# ============================================================
def montar_texto_peca(peca):
    codigo = normalizar_texto(peca.get("codigo", ""))
    descricao = normalizar_texto(peca.get("descricao", ""))

    if codigo and descricao:
        return f"{codigo} - {descricao}"
    if codigo:
        return codigo
    if descricao:
        return descricao

    return "-"


def gerar_pecas_html(ativo, termo_busca, forcar_exibicao=False):
    pecas = ativo.get("pecas", []) or []
    if not pecas:
        return ""

    itens_renderizados = []

    for peca in pecas:
        funcao = normalizar_texto(peca.get("funcao", "")) or "PEÇA"
        texto = montar_texto_peca(peca)
        quantidade = int(peca.get("quantidade", 0) or 0)

        texto_peca = f"{funcao} | {texto} | QTD: {quantidade}"

        if termo_busca and not forcar_exibicao:
            base_busca = f"{funcao} {texto} {quantidade}".lower()
            if termo_busca.lower() not in base_busca:
                continue

        texto_peca_html = destacar_termo_html(texto_peca.upper(), termo_busca)

        itens_renderizados.append(
            f"""
            <li class='tree-item tree-item-peca'>
                <div class='tree-row'>
                    <span class='toggle-placeholder'></span>
                    <div class='node-label node-peca'>
                        {texto_peca_html}
                    </div>
                </div>
            </li>
            """
        )

    if not itens_renderizados:
        return ""

    partes = ["<ul class='children-list pecas-subarvore' style='display:block;'>"]
    partes.extend(itens_renderizados)
    partes.append("</ul>")
    return "".join(partes)


# ============================================================
# BUSCA
# ============================================================
def ativo_corresponde_busca(ativo, termo):
    if not termo:
        return True

    termo = termo.lower()

    campos = [
        str(ativo.get("tag", "")),
        str(ativo.get("descricao", "")),
        str(ativo.get("tipo", "")),
        str(ativo.get("tag_local", "")),
        str(ativo.get("pai", "")),
        str(ativo.get("fabricante", "")),
        str(ativo.get("modelo", "")),
        str(ativo.get("observacoes", "")),
    ]

    if termo in " ".join(campos).lower():
        return True

    pecas = ativo.get("pecas", []) or []
    for p in pecas:
        base_peca = " ".join([
            str(p.get("funcao", "")),
            str(p.get("codigo", "")),
            str(p.get("descricao", "")),
            str(p.get("quantidade", "")),
        ]).lower()
        if termo in base_peca:
            return True

    anexos = (
        (ativo.get("fotos", []) or [])
        + (ativo.get("pdfs", []) or [])
        + (ativo.get("anexos", []) or [])
    )
    if anexos and termo in json.dumps(anexos, ensure_ascii=False).lower():
        return True

    return False


def montar_indices_busca(lista_ativos, mapa_filhos, termo_busca):
    if not termo_busca:
        return None, None

    termo_busca = termo_busca.strip()
    if not termo_busca:
        return None, None

    match_map = {}
    subtree_map = {}

    def calcular_subarvore(ativo):
        chave = chave_ativo(ativo)
        if chave in subtree_map:
            return subtree_map[chave]

        match = ativo_corresponde_busca(ativo, termo_busca)
        filhos = mapa_filhos.get(normalizar_texto(ativo.get("tag", "")), [])

        tem_match_desc = False
        for filho in filhos:
            if calcular_subarvore(filho):
                tem_match_desc = True

        subtree_map[chave] = match or tem_match_desc
        match_map[chave] = match
        return subtree_map[chave]

    for ativo in lista_ativos:
        calcular_subarvore(ativo)

    return match_map, subtree_map


# ============================================================
# VISUAL DO TIPO DE ATIVO
# ============================================================
def classe_tipo(tipo):
    tipo = normalizar_texto(tipo)

    if tipo == "LOCAL":
        return "tipo-local"
    if tipo == "EQUIPAMENTO":
        return "tipo-equipamento"
    if tipo == "COMPONENTE":
        return "tipo-componente"

    return "tipo-default"


# ============================================================
# ANEXOS (FOTOS E PDFs)
# ============================================================
def coletar_itens_anexos(ativo):
    itens = []

    for campo in ["fotos", "pdfs", "anexos"]:
        valores = ativo.get(campo, []) or []

        for item in valores:
            if isinstance(item, dict):
                itens.append(item)
            else:
                itens.append({
                    "arquivo": item,
                    "nome_original": str(item),
                })

    return itens


def ler_bytes_anexo(item):
    if not item:
        return None

    conteudo = item.get("conteudo")

    if isinstance(conteudo, bytes):
        return conteudo

    if isinstance(conteudo, str) and conteudo:
        try:
            return base64.b64decode(conteudo)
        except Exception:
            pass

    storage_key = item.get("storage_key", "")
    if storage_key:
        return ler_bytes_storage_cache(storage_key)

    try:
        return photo_storage.get_bytes(item)
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def montar_anexos_para_painel_cache(ativo_json):
    ativo = json.loads(ativo_json)

    fotos = []
    pdfs = []

    for item in coletar_itens_anexos(ativo):
        nome = nome_item_anexo(item)
        conteudo = ler_bytes_anexo(item)

        if not conteudo:
            continue

        src = bytes_para_data_url(nome, conteudo)

        registro = {
            "nome": normalizar_texto(nome) or "ARQUIVO",
            "src": src,
        }

        if eh_pdf(nome):
            pdfs.append(registro)
        elif eh_imagem(nome):
            fotos.append(registro)

    return fotos, pdfs


def montar_anexos_para_painel(ativo):
    ativo_json = json.dumps(ativo, ensure_ascii=False, sort_keys=True)
    return montar_anexos_para_painel_cache(ativo_json)


# ============================================================
# DADOS DO PAINEL DIREITO
# ============================================================
@st.cache_data(ttl=600, show_spinner=False)
def montar_info_painel_cache(ativo_json):
    ativo = json.loads(ativo_json)
    fotos, pdfs = montar_anexos_para_painel(ativo)

    info = {
        "tag": normalizar_texto(ativo.get("tag", "")),
        "tipo": normalizar_texto(ativo.get("tipo", "")),
        "descricao": normalizar_texto(ativo.get("descricao", "")),
        "tag_local": normalizar_texto(ativo.get("tag_local", "")),
        "pai": obter_pai_relacional(ativo),
        "fabricante": normalizar_texto(ativo.get("fabricante", "")),
        "modelo": normalizar_texto(ativo.get("modelo", "")),
        "observacoes": normalizar_texto(ativo.get("observacoes", "")),
        "pecas": [],
        "fotos": fotos,
        "pdfs": pdfs,
    }

    for p in ativo.get("pecas", []) or []:
        info["pecas"].append({
            "funcao": normalizar_texto(p.get("funcao", "")) or "-",
            "texto": montar_texto_peca(p),
            "quantidade": int(p.get("quantidade", 0) or 0),
        })

    return info


def montar_info_painel(ativo):
    ativo_json = json.dumps(ativo, ensure_ascii=False, sort_keys=True)
    return montar_info_painel_cache(ativo_json)


# ============================================================
# HTML DA ÁRVORE
# ============================================================
def gerar_no_html(
    ativo,
    mapa_filhos,
    termo_busca,
    contador,
    match_map=None,
    subtree_map=None,
    visitados=None,
    forcar_subarvore=False,
):
    if visitados is None:
        visitados = set()

    tag = normalizar_texto(ativo.get("tag", "SEM TAG"))
    descricao = normalizar_texto(ativo.get("descricao", ""))
    tipo = normalizar_texto(ativo.get("tipo", ""))

    chave = chave_ativo(ativo)
    if chave in visitados:
        return "", contador

    visitados.add(chave)

    match_no_atual = (
        match_map.get(chave, True)
        if (match_map is not None and termo_busca)
        else (ativo_corresponde_busca(ativo, termo_busca) if termo_busca else True)
    )

    subarvore_tem_match = (
        subtree_map.get(chave, True)
        if (subtree_map is not None and termo_busca)
        else True
    )

    subarvore_forcada = forcar_subarvore or (bool(termo_busca) and match_no_atual)

    if termo_busca and not subarvore_forcada and not subarvore_tem_match:
        return "", contador

    filhos = mapa_filhos.get(tag, [])

    if termo_busca and not subarvore_forcada:
        filhos_visiveis = [
            filho for filho in filhos
            if subtree_map.get(chave_ativo(filho), False)
        ]
    else:
        filhos_visiveis = filhos

    node_id = f"node_{contador}"
    contador += 1

    possui_filhos_reais = len(filhos_visiveis) > 0
    pecas_html = gerar_pecas_html(ativo, termo_busca, forcar_exibicao=subarvore_forcada)
    possui_pecas_visiveis = bool(pecas_html)
    possui_filhos = possui_filhos_reais or possui_pecas_visiveis

    texto_no = f"{tag} - {descricao} [{tipo}]" if descricao else f"{tag} [{tipo}]"
    texto_no_html = destacar_termo_html(texto_no, termo_busca)

    info_json = html.escape(json.dumps(montar_info_painel(ativo), ensure_ascii=False))

    auto_expandir = False
    if termo_busca:
        if subarvore_forcada:
            auto_expandir = True
        elif any(subtree_map.get(chave_ativo(f), False) for f in filhos_visiveis):
            auto_expandir = True
        elif possui_pecas_visiveis:
            auto_expandir = True

    display_filhos = "block" if auto_expandir else "none"
    simbolo_toggle = "−" if auto_expandir else "+"

    partes = []
    partes.append("<li class='tree-item'>")
    partes.append("<div class='tree-row'>")

    if possui_filhos:
        partes.append(
            f"<button class='toggle-btn' type='button' "
            f"onclick=\"toggleNode('{node_id}', this)\">{simbolo_toggle}</button>"
        )
    else:
        partes.append("<span class='toggle-placeholder'></span>")

    partes.append(
        f"<button "
        f"class='node-label {classe_tipo(tipo)}' "
        f"type='button' "
        f"data-info=\"{info_json}\" "
        f"onclick='selecionarAtivo(this)'>"
        f"{texto_no_html}"
        f"</button>"
    )

    partes.append("</div>")

    if possui_filhos:
        partes.append(
            f"<ul id='{node_id}' class='children-list' style='display:{display_filhos};'>"
        )

        for filho in filhos_visiveis:
            html_filho, contador = gerar_no_html(
                filho,
                mapa_filhos,
                termo_busca,
                contador,
                match_map=match_map,
                subtree_map=subtree_map,
                visitados=visitados.copy(),
                forcar_subarvore=subarvore_forcada,
            )
            partes.append(html_filho)

        if pecas_html:
            partes.append(pecas_html)

        partes.append("</ul>")

    partes.append("</li>")

    return "".join(partes), contador


@st.cache_data(ttl=120, show_spinner=False)
def montar_html_arvore_cache(lista_json, termo_busca):
    lista_ativos = json.loads(lista_json)

    mapa_filhos = montar_mapa_filhos(lista_ativos)
    raizes = montar_raizes(lista_ativos)
    match_map, subtree_map = montar_indices_busca(lista_ativos, mapa_filhos, termo_busca)

    if termo_busca:
        raizes_visiveis = [
            raiz for raiz in raizes
            if subtree_map.get(chave_ativo(raiz), False)
        ]
    else:
        raizes_visiveis = raizes

    partes = ["<ul class='tree-root'>"]

    if raizes_visiveis:
        contador = 1

        for raiz in raizes_visiveis:
            html_raiz, contador = gerar_no_html(
                raiz,
                mapa_filhos,
                termo_busca,
                contador,
                match_map=match_map,
                subtree_map=subtree_map,
            )
            partes.append(html_raiz)
    else:
        partes.append("<div class='sem-resultado'>NENHUM ITEM ENCONTRADO.</div>")

    partes.append("</ul>")
    return "".join(partes)


def montar_html_arvore(lista_ativos, termo_busca):
    lista_json = json.dumps(lista_ativos, ensure_ascii=False, sort_keys=True)
    return montar_html_arvore_cache(lista_json, termo_busca)


# ============================================================
# CSS / TELA PRINCIPAL
# ============================================================
def mostrar_arvore():
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
        }

        section[data-testid="stSidebar"] {
            background: #ffffff !important;
            color: #000000 !important;
        }

        div[data-testid="stToolbar"] {
            background: #ffffff !important;
        }

        input, textarea {
            background: #ffffff !important;
            color: #000000 !important;
        }

        label, p, div, span, h1, h2, h3, h4, h5, h6 {
            color: #000000 !important;
        }

        div[data-testid="stTextInput"] > div,
        div[data-testid="stTextInput"] > div > div {
            overflow: visible !important;
        }

        div[data-testid="stTextInput"] > div > div > input {
            border: 2px solid #c97a00 !important;
            border-radius: 12px !important;
            background: #fffdf7 !important;
            color: #000000 !important;
            box-shadow: 0 0 0 2px rgba(201, 122, 0, 0.10) !important;
            font-weight: 700 !important;
            min-height: 46px !important;
            padding-top: 0.55rem !important;
            padding-bottom: 0.55rem !important;
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
        }

        div[data-testid="stTextInput"] > div > div > input:focus {
            border: 2px solid #ff8c00 !important;
            box-shadow: 0 0 0 4px rgba(255, 140, 0, 0.18) !important;
        }

        div[data-testid="stTextInput"] > div > div > input::placeholder {
            color: #7a5a20 !important;
            opacity: 1 !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

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
            ÁRVORE DE EQUIPAMENTOS
        </h1>
        """,
        unsafe_allow_html=True
    )

    termo_busca = st_keyup(
        "",
        placeholder="PESQUISAR NA ÁRVORE",
        key="pesquisa_arvore"
    ).strip()

    lista, _, _ = carregar_estrutura_cache()

    if not lista:
        st.info("NENHUM ATIVO CADASTRADO AINDA.")
        return

    arvore_html = montar_html_arvore(lista, termo_busca)
    termo_busca_json = json.dumps(termo_busca or "", ensure_ascii=False)

    pagina = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8" />
        <style>
            * {{
                box-sizing: border-box;
            }}

            html, body {{
                margin: 0;
                padding: 0;
                font-family: Arial, Helvetica, sans-serif;
                background: #ffffff;
                color: #000000;
                text-transform: uppercase;
            }}

            .highlight-mark {{
                background: #fff176;
                color: #000000;
                padding: 0 0.18rem;
                border-radius: 4px;
                box-shadow: inset 0 -1px 0 rgba(0,0,0,0.12);
            }}

            .app-shell {{
                display: grid;
                grid-template-columns: minmax(320px, 560px) 10px 1fr;
                width: 100%;
                min-height: 860px;
                border: 1px solid rgba(127,127,127,0.14);
                border-radius: 16px;
                overflow: hidden;
                background: #ffffff;
            }}

            .pane {{
                min-width: 0;
                min-height: 860px;
                background: #ffffff;
            }}

            .pane-left {{
                padding: 1rem;
                overflow: auto;
                background: #ffffff;
            }}

            .pane-right {{
                padding: 1rem;
                overflow: auto;
                background: #ffffff;
                border-left: 1px solid rgba(127, 127, 127, 0.14);
            }}

            .resizer {{
                background: linear-gradient(180deg, #efefef 0%, #e0e0e0 100%);
                cursor: col-resize;
                border-left: 1px solid rgba(0,0,0,0.06);
                border-right: 1px solid rgba(0,0,0,0.06);
            }}

            .tree-root,
            .children-list {{
                list-style: none;
                margin: 0;
                padding-left: 1rem;
            }}

            .tree-root {{
                padding-left: 0;
            }}

            .tree-item {{
                position: relative;
                margin: 0;
                padding: 0.10rem 0;
            }}

            .tree-row {{
                display: flex;
                align-items: flex-start;
                gap: 0.42rem;
                width: 100%;
            }}

            .toggle-btn,
            .toggle-placeholder {{
                width: 22px;
                min-width: 22px;
                height: 22px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                margin-top: 0.12rem;
            }}

            .toggle-btn {{
                border: 1px solid rgba(0,0,0,0.10);
                border-radius: 6px;
                background: #f8f8f8;
                cursor: pointer;
                font-weight: 800;
                line-height: 1;
                color: #333333;
            }}

            .toggle-btn:hover {{
                background: #efefef;
            }}

            .toggle-placeholder {{
                visibility: hidden;
            }}

            .node-label {{
                border: none;
                background: transparent;
                text-align: left;
                padding: 0.20rem 0.15rem;
                margin: 0;
                cursor: pointer;
                font-size: 0.94rem;
                line-height: 1.35;
                font-weight: 700;
                color: #000000;
                width: 100%;
                border-radius: 8px;
            }}

            .node-label:hover {{
                background: rgba(201, 122, 0, 0.08);
            }}

            .node-label.selecionado {{
                background: rgba(201, 122, 0, 0.14);
                outline: 1px solid rgba(201, 122, 0, 0.30);
            }}

            .node-peca {{
                font-size: 0.88rem;
                font-weight: 700;
                color: #2f2f2f;
                padding: 0.18rem 0.15rem;
            }}

            .tipo-local {{
                color: #7a3e00;
            }}

            .tipo-equipamento {{
                color: #9a5a00;
            }}

            .tipo-componente {{
                color: #bb6b00;
            }}

            .tipo-default {{
                color: #222222;
            }}

            .panel-card {{
                width: 100%;
                border: 1px solid rgba(127,127,127,0.14);
                border-radius: 16px;
                background: #ffffff;
                overflow: hidden;
            }}

            .panel-empty {{
                padding: 1.2rem;
                color: #5b5b5b;
                font-weight: 700;
            }}

            .panel-header {{
                padding: 0.95rem 1rem;
                border-bottom: 1px solid rgba(127,127,127,0.14);
                background: #fff8ef;
            }}

            .panel-title {{
                font-size: 1.1rem;
                font-weight: 800;
                color: #000000;
                overflow-wrap: anywhere;
            }}

            .panel-subtitle {{
                margin-top: 0.25rem;
                color: #5e4b27;
                font-weight: 700;
            }}

            .panel-body {{
                padding: 1rem;
            }}

            .panel-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(180px, 1fr));
                gap: 0.85rem;
                margin-bottom: 1rem;
            }}

            .info-box {{
                border: 1px solid rgba(127,127,127,0.14);
                border-radius: 12px;
                padding: 0.75rem 0.85rem;
                background: #ffffff;
            }}

            .info-label {{
                font-size: 0.78rem;
                font-weight: 800;
                color: #7a5a20;
                margin-bottom: 0.2rem;
            }}

            .info-value {{
                font-size: 0.95rem;
                font-weight: 700;
                color: #000000;
                overflow-wrap: anywhere;
                word-break: break-word;
            }}

            .secao-titulo {{
                margin: 1rem 0 0.55rem 0;
                font-size: 0.96rem;
                font-weight: 800;
                color: #000000;
            }}

            .peca-card,
            .arquivo-card {{
                border: 1px solid rgba(127,127,127,0.14);
                border-radius: 12px;
                padding: 0.7rem 0.8rem;
                margin-bottom: 0.55rem;
                background: #fffdf9;
            }}

            .arquivo-actions {{
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-top: 0.55rem;
            }}

            .arquivo-btn {{
                border: 1px solid rgba(0,0,0,0.10);
                border-radius: 10px;
                background: #ffffff;
                padding: 0.45rem 0.7rem;
                font-weight: 800;
                cursor: pointer;
            }}

            .arquivo-btn:hover {{
                background: #f3f3f3;
            }}

            .sem-resultado {{
                padding: 1rem 0.5rem;
                font-weight: 800;
                color: #666666;
            }}

            .modal-overlay {{
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.72);
                display: none;
                z-index: 9999;
                align-items: center;
                justify-content: center;
            }}

            .modal-overlay.ativo {{
                display: flex;
            }}

            .modal-box {{
                width: min(96vw, 1320px);
                height: min(92vh, 920px);
                background: #101010;
                border-radius: 16px;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                box-shadow: 0 10px 35px rgba(0,0,0,0.35);
            }}

            .modal-header {{
                width: 100%;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.8rem;
                padding: 0.75rem 0.9rem;
                background: rgba(0,0,0,0.62);
            }}

            .modal-title {{
                color: #ffffff;
                font-weight: 800;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
            }}

            .modal-actions {{
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
            }}

            .modal-btn {{
                border: none;
                border-radius: 10px;
                padding: 0.5rem 0.8rem;
                background: rgba(255,255,255,0.92);
                color: #000000;
                cursor: pointer;
                font-weight: 800;
                text-decoration: none;
            }}

            .modal-conteudo {{
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #111111;
                padding-top: 60px;
            }}

            .modal-conteudo img {{
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }}

            .modal-conteudo iframe {{
                width: 100%;
                height: 100%;
                border: none;
                background: #ffffff;
            }}

            @media (max-width: 960px) {{
                .app-shell {{
                    grid-template-columns: 1fr;
                }}

                .resizer {{
                    display: none;
                }}

                .pane-right {{
                    border-left: none;
                    border-top: 1px solid rgba(127, 127, 127, 0.14);
                }}

                .panel-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="app-shell" id="appShell">
            <div class="pane pane-left">
                {arvore_html}
            </div>

            <div class="resizer" id="resizer"></div>

            <div class="pane pane-right">
                <div class="panel-card" id="infoPanel">
                    <div class="panel-empty">
                        SELECIONE UM ITEM NA ÁRVORE PARA VER AS INFORMAÇÕES
                    </div>
                </div>
            </div>
        </div>

        <div class="modal-overlay" id="modalOverlay" onclick="fecharModal(event)">
            <div class="modal-box">
                <div class="modal-header">
                    <div class="modal-title" id="modalTitle">VISUALIZAÇÃO</div>
                    <div class="modal-actions" id="modalActions"></div>
                </div>
                <div class="modal-conteudo" id="modalConteudo"></div>
            </div>
        </div>

        <script>
            let painelAtual = null;
            const termoBuscaAtual = {termo_busca_json};

            function toggleNode(nodeId, btn) {{
                const alvo = document.getElementById(nodeId);
                if (!alvo) return;

                const aberto = alvo.style.display === "block";
                alvo.style.display = aberto ? "none" : "block";
                btn.textContent = aberto ? "+" : "−";
            }}

            function escapeHtml(texto) {{
                return String(texto || "")
                    .replaceAll("&", "&amp;")
                    .replaceAll("<", "&lt;")
                    .replaceAll(">", "&gt;")
                    .replaceAll('"', "&quot;")
                    .replaceAll("'", "&#039;");
            }}

            function montarInfoBox(rotulo, valor) {{
                const valorFinal = String(valor || "-").trim() || "-";
                return `
                    <div class="info-box">
                        <div class="info-label">${{escapeHtml(rotulo)}}</div>
                        <div class="info-value">${{escapeHtml(valorFinal)}}</div>
                    </div>
                `;
            }}

            function abrirImagem(nome, src) {{
                const overlay = document.getElementById("modalOverlay");
                const conteudo = document.getElementById("modalConteudo");
                const actions = document.getElementById("modalActions");
                const titulo = document.getElementById("modalTitle");

                if (!overlay || !conteudo || !actions || !titulo) return;

                titulo.textContent = nome || "IMAGEM";
                actions.innerHTML = `
                    <a class="modal-btn" href="${{src}}" download="${{escapeHtml(nome || 'imagem')}}">BAIXAR</a>
                    <button class="modal-btn" type="button" onclick="fecharModal()">FECHAR</button>
                `;
                conteudo.innerHTML = `<img src="${{src}}" alt="${{escapeHtml(nome || 'imagem')}}" />`;
                overlay.classList.add("ativo");
            }}

            function abrirPdf(nome, src) {{
                const overlay = document.getElementById("modalOverlay");
                const conteudo = document.getElementById("modalConteudo");
                const actions = document.getElementById("modalActions");
                const titulo = document.getElementById("modalTitle");

                if (!overlay || !conteudo || !actions || !titulo) return;

                titulo.textContent = nome || "PDF";
                actions.innerHTML = `
                    <a class="modal-btn" href="${{src}}" download="${{escapeHtml(nome || 'arquivo.pdf')}}">BAIXAR</a>
                    <button class="modal-btn" type="button" onclick="fecharModal()">FECHAR</button>
                `;
                conteudo.innerHTML = `
                    <iframe src="${{src}}" title="${{escapeHtml(nome || 'PDF')}}"></iframe>
                `;
                overlay.classList.add("ativo");
            }}

            function fecharModal(event) {{
                if (event) {{
                    const modalBox = document.querySelector(".modal-box");
                    if (modalBox && modalBox.contains(event.target)) {{
                        return;
                    }}
                }}

                const overlay = document.getElementById("modalOverlay");
                const conteudo = document.getElementById("modalConteudo");
                const actions = document.getElementById("modalActions");
                const titulo = document.getElementById("modalTitle");

                if (!overlay || !conteudo || !actions || !titulo) return;

                overlay.classList.remove("ativo");
                conteudo.innerHTML = "";
                actions.innerHTML = "";
                titulo.textContent = "VISUALIZAÇÃO";
            }}

            function selecionarAtivo(botao) {{
                try {{
                    const bruto = botao.getAttribute("data-info");
                    if (!bruto) return;

                    const info = JSON.parse(bruto);
                    painelAtual = info;

                    document.querySelectorAll(".node-label.selecionado").forEach(el => {{
                        el.classList.remove("selecionado");
                    }});
                    botao.classList.add("selecionado");

                    const panel = document.getElementById("infoPanel");
                    if (!panel) return;

                    let pecasHtml = "";
                    if (Array.isArray(info.pecas) && info.pecas.length) {{
                        pecasHtml += `<div class="secao-titulo">PEÇAS</div>`;
                        info.pecas.forEach(peca => {{
                            pecasHtml += `
                                <div class="peca-card">
                                    <div><strong>FUNÇÃO:</strong> ${{escapeHtml(peca.funcao || "-")}}</div>
                                    <div><strong>PEÇA:</strong> ${{escapeHtml(peca.texto || "-")}}</div>
                                    <div><strong>QTD:</strong> ${{escapeHtml(peca.quantidade || 0)}}</div>
                                </div>
                            `;
                        }});
                    }}

                    let fotosHtml = "";
                    if (Array.isArray(info.fotos) && info.fotos.length) {{
                        fotosHtml += `<div class="secao-titulo">IMAGENS</div>`;
                        info.fotos.forEach((foto, i) => {{
                            fotosHtml += `
                                <div class="arquivo-card">
                                    <div><strong>ARQUIVO:</strong> ${{escapeHtml(foto.nome || `IMAGEM ${{i+1}}`)}}</div>
                                    <div class="arquivo-actions">
                                        <button class="arquivo-btn" type="button" onclick="abrirImagem('${{String(foto.nome || '').replaceAll("'", "\\\\'")}}', '${{foto.src}}')">VISUALIZAR</button>
                                    </div>
                                </div>
                            `;
                        }});
                    }}

                    let pdfsHtml = "";
                    if (Array.isArray(info.pdfs) && info.pdfs.length) {{
                        pdfsHtml += `<div class="secao-titulo">PDFS</div>`;
                        info.pdfs.forEach((pdf, i) => {{
                            pdfsHtml += `
                                <div class="arquivo-card">
                                    <div><strong>ARQUIVO:</strong> ${{escapeHtml(pdf.nome || `PDF ${{i+1}}`)}}</div>
                                    <div class="arquivo-actions">
                                        <button class="arquivo-btn" type="button" onclick="abrirPdf('${{String(pdf.nome || '').replaceAll("'", "\\\\'")}}', '${{pdf.src}}')">VISUALIZAR</button>
                                    </div>
                                </div>
                            `;
                        }});
                    }}

                    panel.innerHTML = `
                        <div class="panel-header">
                            <div class="panel-title">${{escapeHtml(info.tag || "SEM TAG")}}</div>
                            <div class="panel-subtitle">${{escapeHtml(info.descricao || "-")}}</div>
                        </div>
                        <div class="panel-body">
                            <div class="panel-grid">
                                ${{montarInfoBox("TIPO", info.tipo)}}
                                ${{montarInfoBox("TAG LOCAL", info.tag_local)}}
                                ${{montarInfoBox("PAI", info.pai)}}
                                ${{montarInfoBox("FABRICANTE", info.fabricante)}}
                                ${{montarInfoBox("MODELO", info.modelo)}}
                                ${{montarInfoBox("OBSERVAÇÕES", info.observacoes)}}
                            </div>
                            ${{pecasHtml}}
                            ${{fotosHtml}}
                            ${{pdfsHtml}}
                        </div>
                    `;
                }} catch (e) {{
                    console.error(e);
                }}
            }}

            function habilitarResize() {{
                const shell = document.getElementById("appShell");
                const resizer = document.getElementById("resizer");

                if (!shell || !resizer) return;
                if (window.innerWidth <= 960) return;

                let pressionado = false;

                resizer.addEventListener("mousedown", function() {{
                    pressionado = true;
                    document.body.style.cursor = "col-resize";
                    document.body.style.userSelect = "none";
                }});

                window.addEventListener("mousemove", function(e) {{
                    if (!pressionado) return;

                    const rect = shell.getBoundingClientRect();
                    let left = e.clientX - rect.left;

                    const minLeft = 280;
                    const minRight = 320;

                    if (left < minLeft) left = minLeft;
                    if (left > rect.width - minRight) left = rect.width - minRight;

                    shell.style.gridTemplateColumns = `${{left}}px 10px 1fr`;
                }});

                window.addEventListener("mouseup", function() {{
                    pressionado = false;
                    document.body.style.cursor = "";
                    document.body.style.userSelect = "";
                }});
            }}

            document.addEventListener("keydown", function(e) {{
                if (e.key === "Escape") {{
                    fecharModal();
                }}
            }});

            habilitarResize();
        </script>
    </body>
    </html>
    """

    components.html(pagina, height=900, scrolling=True)


if __name__ == "__main__":
    mostrar_arvore()
