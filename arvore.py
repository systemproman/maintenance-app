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


@st.cache_data(ttl=120, show_spinner=False)
def ler_bytes_storage_cache(storage_key):
    if not storage_key:
        return None
    try:
        return photo_storage.get_bytes({"storage_key": storage_key})
    except Exception:
        return None


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


# ============================================================
# DADOS DOS ATIVOS
# ============================================================

@st.cache_data(ttl=10, show_spinner=False)
def carregar_ativos_cache():
    return asset_repo.list_assets()


def carregar_ativos():
    return carregar_ativos_cache()


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
    if pecas:
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


def arvore_tem_match(ativo, mapa_filhos, termo, visitados=None):
    if visitados is None:
        visitados = set()

    tag = normalizar_texto(ativo.get("tag", ""))
    chave_visita = tag or f"SEM_TAG_{id(ativo)}"

    if chave_visita in visitados:
        return False

    visitados.add(chave_visita)

    if ativo_corresponde_busca(ativo, termo):
        return True

    filhos = mapa_filhos.get(tag, [])

    for filho in filhos:
        if arvore_tem_match(filho, mapa_filhos, termo, visitados.copy()):
            return True

    return False


def descendente_tem_match(ativo, mapa_filhos, termo, visitados=None):
    if not termo:
        return False

    if visitados is None:
        visitados = set()

    tag = normalizar_texto(ativo.get("tag", ""))
    chave_visita = tag or f"SEM_TAG_{id(ativo)}"

    if chave_visita in visitados:
        return False

    visitados.add(chave_visita)

    filhos = mapa_filhos.get(tag, [])

    for filho in filhos:
        if ativo_corresponde_busca(filho, termo):
            return True
        if descendente_tem_match(filho, mapa_filhos, termo, visitados.copy()):
            return True

    return False


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


@st.cache_data(ttl=120, show_spinner=False)
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

@st.cache_data(ttl=120, show_spinner=False)
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
    visitados=None,
    forcar_subarvore=False,
):
    if visitados is None:
        visitados = set()

    tag = normalizar_texto(ativo.get("tag", "SEM TAG"))
    descricao = normalizar_texto(ativo.get("descricao", ""))
    tipo = normalizar_texto(ativo.get("tipo", ""))

    chave_visita = tag or f"SEM_TAG_{id(ativo)}"
    if chave_visita in visitados:
        return "", contador

    visitados.add(chave_visita)

    match_no_atual = ativo_corresponde_busca(ativo, termo_busca) if termo_busca else True
    subarvore_forcada = forcar_subarvore or (bool(termo_busca) and match_no_atual)

    if termo_busca and not subarvore_forcada and not arvore_tem_match(ativo, mapa_filhos, termo_busca):
        return "", contador

    filhos = mapa_filhos.get(tag, [])

    if termo_busca and not subarvore_forcada:
        filhos_visiveis = [
            filho for filho in filhos
            if arvore_tem_match(filho, mapa_filhos, termo_busca)
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
        elif possui_filhos_reais and descendente_tem_match(ativo, mapa_filhos, termo_busca):
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
                visitados.copy(),
                subarvore_forcada,
            )
            partes.append(html_filho)

        if pecas_html:
            partes.append(pecas_html)

        partes.append("</ul>")

    partes.append("</li>")

    return "".join(partes), contador


def montar_html_arvore(lista_ativos, termo_busca):
    mapa_filhos = montar_mapa_filhos(lista_ativos)
    raizes = montar_raizes(lista_ativos)

    if termo_busca:
        raizes_visiveis = [
            raiz for raiz in raizes
            if arvore_tem_match(raiz, mapa_filhos, termo_busca)
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
            )
            partes.append(html_raiz)
    else:
        partes.append("<div class='sem-resultado'>NENHUM ITEM ENCONTRADO.</div>")

    partes.append("</ul>")

    return "".join(partes)


# ============================================================
# TELA PRINCIPAL
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

        div[data-testid="stTextInput"] > div > div > input {
            border: 2px solid #c97a00 !important;
            border-radius: 12px !important;
            background: #fffdf7 !important;
            color: #000000 !important;
            box-shadow: 0 0 0 2px rgba(201, 122, 0, 0.10) !important;
            font-weight: 700 !important;
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

    lista = carregar_ativos()

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
                box-shadow: inset 0 -1px 0 rgba(0,0,0,0.10);
            }}

            .app-shell {{
                display: grid;
                grid-template-columns: minmax(320px, 1fr) 10px minmax(380px, 0.95fr);
                min-height: 840px;
                border: 1px solid rgba(127, 127, 127, 0.16);
                border-radius: 18px;
                overflow: hidden;
                background: #ffffff;
            }}

            .pane {{
                min-width: 0;
                min-height: 840px;
                background: #ffffff;
            }}

            .pane-left {{
                padding: 0.9rem;
                overflow: auto;
                background: #ffffff;
            }}

            .pane-right {{
                padding: 0.9rem;
                overflow: auto;
                border-left: 1px solid rgba(127, 127, 127, 0.14);
                background: #ffffff;
            }}

            .resizer {{
                cursor: col-resize;
                background:
                    linear-gradient(
                        to right,
                        rgba(127,127,127,0.08) 0%,
                        rgba(127,127,127,0.18) 50%,
                        rgba(127,127,127,0.08) 100%
                    );
                position: relative;
            }}

            .resizer::after {{
                content: "";
                position: absolute;
                top: 50%;
                left: 50%;
                width: 4px;
                height: 58px;
                transform: translate(-50%, -50%);
                border-radius: 999px;
                background: rgba(127,127,127,0.24);
            }}

            .tree-root,
            .tree-root ul {{
                list-style: none;
                margin: 0;
                padding: 0;
            }}

            .tree-root ul {{
                position: relative;
                margin-left: 1.35rem;
                padding-left: 0.95rem;
            }}

            .tree-root ul::before {{
                content: "";
                position: absolute;
                left: 0.35rem;
                top: 0;
                bottom: 1.05rem;
                border-left: 1px solid rgba(127, 127, 127, 0.32);
            }}

            .tree-item {{
                position: relative;
                margin: 0.28rem 0;
            }}

            .tree-item::before {{
                content: "";
                position: absolute;
                left: -0.98rem;
                top: 1.08rem;
                width: 0.9rem;
                border-top: 1px solid rgba(127, 127, 127, 0.32);
            }}

            .tree-item-peca::before {{
                border-top: 1px dashed rgba(127, 127, 127, 0.42);
            }}

            .tree-row {{
                display: flex;
                align-items: flex-start;
                gap: 0.45rem;
                min-height: 2rem;
            }}

            .toggle-btn,
            .toggle-placeholder {{
                width: 1.4rem;
                min-width: 1.4rem;
                height: 1.4rem;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 6px;
                margin-top: 0.25rem;
                flex: 0 0 auto;
            }}

            .toggle-btn {{
                border: 1px solid rgba(127, 127, 127, 0.30);
                background: rgba(127, 127, 127, 0.08);
                color: inherit;
                cursor: pointer;
                font-weight: 700;
                line-height: 1;
            }}

            .toggle-btn:hover {{
                background: rgba(127, 127, 127, 0.16);
            }}

            .toggle-placeholder {{
                opacity: 0;
            }}

            .children-list {{
                margin-top: 0.18rem;
            }}

            .pecas-subarvore {{
                margin-top: 0.15rem;
            }}

            .node-label {{
                border: 1px solid transparent;
                color: #000000;
                cursor: pointer;
                text-align: left;
                padding: 0.46rem 0.78rem;
                border-radius: 12px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 18px;
                line-height: 1.4;
                width: 100%;
                max-width: 100%;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
                transition: 0.16s ease;
                font-weight: 700;
            }}

            .node-label:hover {{
                transform: translateY(-1px);
                box-shadow: 0 6px 18px rgba(0,0,0,0.08);
            }}

            .node-label.selected {{
                outline: 2px solid rgba(70, 120, 255, 0.30);
                box-shadow: 0 8px 20px rgba(0,0,0,0.10);
            }}

            .node-peca {{
                background: #fff7e6;
                border: 1px dashed rgba(201, 122, 0, 0.45);
                font-size: 15px;
                font-weight: 700;
                cursor: default;
            }}

            .node-peca:hover {{
                transform: none;
                box-shadow: none;
            }}

            .tipo-local {{
                background: #FFD700;
                border-color: rgba(70, 120, 255, 0.28);
            }}

            .tipo-equipamento {{
                background: #FFA500;
                border-color: rgba(255, 180, 0, 0.30);
            }}

            .tipo-componente {{
                background: #FF8C00;
                border-color: rgba(30, 180, 110, 0.28);
            }}

            .tipo-default {{
                background: rgba(127, 127, 127, 0.08);
                border-color: rgba(127, 127, 127, 0.20);
            }}

            .panel-card {{
                border: 1px solid rgba(127, 127, 127, 0.16);
                background: #ffffff;
                border-radius: 16px;
                padding: 1rem;
            }}

            .panel-empty {{
                min-height: 320px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                opacity: 0.72;
                font-weight: 700;
                letter-spacing: 0.3px;
                color: #000000;
            }}

            .asset-title {{
                font-family: Consolas, "Courier New", monospace;
                font-size: 1.35rem;
                font-weight: 700;
                line-height: 1.45;
                margin-bottom: 1rem;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
                color: #000000;
            }}

            .section-title {{
                font-size: 0.9rem;
                font-weight: 800;
                letter-spacing: 0.3px;
                margin: 1rem 0 0.65rem 0;
                color: #000000;
                display: flex;
                align-items: center;
                gap: 0.45rem;
            }}

            .info-grid {{
                display: grid;
                gap: 0.42rem;
            }}

            .info-line {{
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
                line-height: 1.45;
                color: #000000;
            }}

            .info-line b {{
                margin-right: 0.28rem;
            }}

            .pecas-lista {{
                margin: 0;
                padding-left: 1.1rem;
                color: #000000;
            }}

            .pecas-lista li {{
                margin-bottom: 0.3rem;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
                line-height: 1.45;
                color: #000000;
            }}

            .sem-resultado {{
                padding: 0.95rem 0.35rem;
                opacity: 0.74;
                font-weight: 700;
                color: #000000;
            }}

            .anexos-bloco {{
                margin-top: 1rem;
                border: 1px solid rgba(127,127,127,0.16);
                border-radius: 14px;
                padding: 0.85rem;
                background: rgba(127,127,127,0.03);
            }}

            .fotos-grid {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.7rem;
            }}

            .foto-card {{
                border: 1px solid rgba(127,127,127,0.15);
                border-radius: 12px;
                background: #ffffff;
                padding: 0.35rem;
                cursor: pointer;
                width: 120px;
            }}

            .foto-card:hover {{
                box-shadow: 0 6px 18px rgba(0,0,0,0.08);
                transform: translateY(-1px);
            }}

            .foto-card img {{
                width: 100%;
                height: 100px;
                object-fit: cover;
                display: block;
                border-radius: 8px;
            }}

            .foto-nome {{
                margin-top: 0.35rem;
                font-size: 11px;
                font-weight: 700;
                text-align: center;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
            }}

            .pdf-lista {{
                display: grid;
                gap: 0.55rem;
            }}

            .pdf-card {{
                border: 1px solid rgba(127,127,127,0.15);
                border-radius: 12px;
                background: #ffffff;
                padding: 0.75rem;
                cursor: pointer;
            }}

            .pdf-card:hover {{
                box-shadow: 0 6px 18px rgba(0,0,0,0.08);
                transform: translateY(-1px);
            }}

            .pdf-topo {{
                display: flex;
                align-items: center;
                gap: 0.6rem;
            }}

            .pdf-icone {{
                font-size: 1.2rem;
            }}

            .pdf-nome {{
                font-weight: 700;
                overflow-wrap: anywhere;
                word-break: break-word;
                white-space: normal;
            }}

            .vazio-anexo {{
                opacity: 0.72;
                padding: 0.5rem 0.2rem;
                font-weight: 700;
            }}

            .modal-overlay {{
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.78);
                display: none;
                align-items: center;
                justify-content: center;
                z-index: 99999;
                padding: 1rem;
            }}

            .modal-overlay.ativo {{
                display: flex;
            }}

            .modal-box {{
                position: relative;
                width: min(96vw, 1200px);
                height: min(92vh, 900px);
                background: #111111;
                border-radius: 14px;
                overflow: hidden;
                box-shadow: 0 18px 50px rgba(0,0,0,0.35);
            }}

            .modal-header {{
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                z-index: 3;
                display: flex;
                justify-content: space-between;
                align-items: center;
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

            function selecionarAtivo(el) {{
                document.querySelectorAll(".node-label.selected").forEach(n => {{
                    n.classList.remove("selected");
                }});

                el.classList.add("selected");

                const raw = el.getAttribute("data-info");
                if (!raw) return;

                painelAtual = JSON.parse(raw);
                renderPainelDireito();
            }}

            function escapeHtml(text) {{
                const div = document.createElement("div");
                div.textContent = String(text ?? "");
                return div.innerHTML;
            }}

            function escapeJs(text) {{
                return String(text || "")
                    .replace(/\\\\/g, "\\\\\\\\")
                    .replace(/'/g, "\\\\'")
                    .replace(/"/g, '&quot;')
                    .replace(/\\n/g, ' ')
                    .replace(/\\r/g, ' ');
            }}

            function escapeRegExp(text) {{
                return String(text || "").replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&");
            }}

            function highlightHtml(text) {{
                const valor = String(text ?? "");
                const termo = String(termoBuscaAtual || "").trim();

                if (!termo) {{
                    return escapeHtml(valor);
                }}

                const regex = new RegExp(`(${{escapeRegExp(termo)}})`, "ig");
                return escapeHtml(valor).replace(regex, '<mark class="highlight-mark">$1</mark>');
            }}

            function renderPainelDireito() {{
                const panel = document.getElementById("infoPanel");

                if (!painelAtual) {{
                    panel.innerHTML = `
                        <div class="panel-empty">
                            SELECIONE UM ITEM NA ÁRVORE PARA VER AS INFORMAÇÕES
                        </div>
                    `;
                    return;
                }}

                const titulo = painelAtual.descricao
                    ? `${{painelAtual.tag}} - ${{painelAtual.descricao}} [${{painelAtual.tipo}}]`
                    : `${{painelAtual.tag}} [${{painelAtual.tipo}}]`;

                const infoLinhas = [];

                addInfoLinha(infoLinhas, "TAG", painelAtual.tag);
                addInfoLinha(infoLinhas, "TIPO", painelAtual.tipo);
                addInfoLinha(infoLinhas, "DESCRIÇÃO", painelAtual.descricao);
                addInfoLinha(infoLinhas, "PAI", painelAtual.pai);
                addInfoLinha(infoLinhas, "TAG COMPONENTE", painelAtual.tag_local);
                addInfoLinha(infoLinhas, "FABRICANTE", painelAtual.fabricante);
                addInfoLinha(infoLinhas, "MODELO", painelAtual.modelo);
                addInfoLinha(infoLinhas, "OBSERVAÇÕES", painelAtual.observacoes);
                addInfoLinha(infoLinhas, "QTD. FOTOS", String((painelAtual.fotos || []).length));
                addInfoLinha(infoLinhas, "QTD. PDFs", String((painelAtual.pdfs || []).length));

                let pecasHtml = "";
                const pecas = painelAtual.pecas || [];

                if (pecas.length) {{
                    pecasHtml += `<div class="section-title">PEÇAS</div>`;
                    pecasHtml += `<ul class="pecas-lista">`;

                    for (const p of pecas) {{
                        pecasHtml +=
                            `<li><b>${{highlightHtml(String(p.funcao).toUpperCase())}}</b> | ` +
                            `${{highlightHtml(String(p.texto).toUpperCase())}} | ` +
                            `QTD: ${{highlightHtml(String(p.quantidade).toUpperCase())}}</li>`;
                    }}

                    pecasHtml += `</ul>`;
                }}

                panel.innerHTML = `
                    <div class="asset-title">${{highlightHtml(titulo.toUpperCase())}}</div>

                    <div class="section-title">DETALHES</div>
                    <div class="info-grid">
                        ${{infoLinhas.join("")}}
                    </div>

                    ${{pecasHtml}}

                    <div class="anexos-bloco">
                        <div class="section-title">📎 ANEXOS</div>

                        <div class="section-title">🖼️ FOTOS</div>
                        <div id="fotosGrid"></div>

                        <div class="section-title">📄 PDFS</div>
                        <div id="pdfLista"></div>
                    </div>
                `;

                renderFotosPainel();
                renderPdfsPainel();
            }}

            function addInfoLinha(lista, rotulo, valor) {{
                if (!valor) return;

                lista.push(
                    `<div class="info-line"><b>${{escapeHtml(rotulo)}}:</b> ` +
                    `${{highlightHtml(String(valor).toUpperCase())}}</div>`
                );
            }}

            function renderFotosPainel() {{
                const fotosGrid = document.getElementById("fotosGrid");
                if (!fotosGrid || !painelAtual) return;

                const fotos = painelAtual.fotos || [];

                if (!fotos.length) {{
                    fotosGrid.innerHTML = `<div class="vazio-anexo">SEM FOTOS</div>`;
                    return;
                }}

                let htmlFotos = `<div class="fotos-grid">`;

                fotos.forEach((foto) => {{
                    htmlFotos += `
                        <div
                            class="foto-card"
                            title="${{escapeHtml(foto.nome)}}"
                            onclick="abrirImagemModal('${{foto.src}}', '${{escapeJs(foto.nome)}}')"
                        >
                            <img src="${{foto.src}}" alt="${{escapeHtml(foto.nome)}}" />
                            <div class="foto-nome">${{highlightHtml(String(foto.nome).toUpperCase())}}</div>
                        </div>
                    `;
                }});

                htmlFotos += `</div>`;
                fotosGrid.innerHTML = htmlFotos;
            }}

            function renderPdfsPainel() {{
                const pdfLista = document.getElementById("pdfLista");
                if (!pdfLista || !painelAtual) return;

                const pdfs = painelAtual.pdfs || [];

                if (!pdfs.length) {{
                    pdfLista.innerHTML = `<div class="vazio-anexo">SEM PDFS</div>`;
                    return;
                }}

                let htmlPdf = `<div class="pdf-lista">`;

                pdfs.forEach((pdf) => {{
                    htmlPdf += `
                        <div
                            class="pdf-card"
                            onclick="abrirPdfModal('${{pdf.src}}', '${{escapeJs(pdf.nome)}}')"
                            title="${{escapeHtml(pdf.nome)}}"
                        >
                            <div class="pdf-topo">
                                <div class="pdf-icone">📄</div>
                                <div class="pdf-nome">${{highlightHtml(String(pdf.nome).toUpperCase())}}</div>
                            </div>
                        </div>
                    `;
                }});

                htmlPdf += `</div>`;
                pdfLista.innerHTML = htmlPdf;
            }}

            function abrirImagemModal(src, nome) {{
                const overlay = document.getElementById("modalOverlay");
                const conteudo = document.getElementById("modalConteudo");
                const titulo = document.getElementById("modalTitle");
                const actions = document.getElementById("modalActions");

                if (!overlay || !conteudo || !titulo || !actions) return;

                titulo.textContent = String(nome || "IMAGEM").toUpperCase();

                actions.innerHTML = `
                    <a class="modal-btn" href="${{src}}" download="${{escapeHtml(nome || 'imagem')}}">DOWNLOAD</a>
                    <button class="modal-btn" type="button" onclick="fecharModal()">FECHAR</button>
                `;

                conteudo.innerHTML = `
                    <img src="${{src}}" alt="${{escapeHtml(nome || 'IMAGEM')}}" />
                `;

                overlay.classList.add("ativo");
            }}

            function abrirPdfModal(src, nome) {{
                const overlay = document.getElementById("modalOverlay");
                const conteudo = document.getElementById("modalConteudo");
                const titulo = document.getElementById("modalTitle");
                const actions = document.getElementById("modalActions");

                if (!overlay || !conteudo || !titulo || !actions) return;

                titulo.textContent = String(nome || "PDF").toUpperCase();

                actions.innerHTML = `
                    <a class="modal-btn" href="${{src}}" download="${{escapeHtml(nome || 'arquivo.pdf')}}">DOWNLOAD</a>
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