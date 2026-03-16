import os
import re
import json
import uuid
from typing import Optional

import streamlit as st
from supabase import create_client, Client


ARQUIVO_ATIVOS = "ativos.json"
ARQUIVO_PECAS = "pecas.json"
PASTA_STORAGE_FOTOS = os.path.join("storage", "ativos")


# ==========================================================
# UTILITÁRIOS LOCAIS
# ==========================================================
def garantir_pasta(caminho):
    os.makedirs(caminho, exist_ok=True)


def carregar_json(nome_arquivo):
    if not os.path.exists(nome_arquivo):
        return []

    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def salvar_json(nome_arquivo, dados):
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)


def normalizar_tag(valor):
    return str(valor or "").strip().upper()


def normalizar_tag_storage(valor):
    tag = normalizar_tag(valor)

    # Mantém só caracteres seguros para path no Supabase Storage
    # Ex.: "PH-01 [HC-01]" -> "PH-01_HC-01"
    tag = re.sub(r"[^A-Z0-9._-]+", "_", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")

    if not tag:
        tag = "SEM_TAG"

    return tag


def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_bucket_name() -> str:
    return st.secrets.get("SUPABASE_BUCKET", "ativos")


# ==========================================================
# STORAGE
# ==========================================================
class PhotoStorage:
    def save_uploaded_files(self, uploaded_files, ativo_tag):
        raise NotImplementedError

    def delete_many(self, fotos):
        raise NotImplementedError

    def get_bytes(self, foto):
        raise NotImplementedError


class LocalPhotoStorage(PhotoStorage):
    def __init__(self, pasta_base=PASTA_STORAGE_FOTOS):
        self.pasta_base = pasta_base
        garantir_pasta(self.pasta_base)

    def save_uploaded_files(self, uploaded_files, ativo_tag):
        if not uploaded_files:
            return []

        pasta_ativo = os.path.join(self.pasta_base, normalizar_tag_storage(ativo_tag))
        garantir_pasta(pasta_ativo)

        fotos_salvas = []

        for arquivo in uploaded_files:
            extensao = os.path.splitext(arquivo.name)[1].lower()
            nome_storage = f"{uuid.uuid4().hex}{extensao}"
            caminho_final = os.path.join(pasta_ativo, nome_storage)

            with open(caminho_final, "wb") as destino:
                destino.write(arquivo.getbuffer())

            fotos_salvas.append({
                "id": uuid.uuid4().hex,
                "nome_original": arquivo.name,
                "mime": arquivo.type,
                "storage_key": caminho_final.replace("\\", "/")
            })

        return fotos_salvas

    def delete_many(self, fotos):
        for foto in fotos or []:
            caminho = foto.get("storage_key", "")
            if caminho and os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except OSError:
                    pass

        pastas_possiveis = {
            os.path.dirname(f.get("storage_key", ""))
            for f in (fotos or [])
            if f.get("storage_key")
        }

        for pasta in pastas_possiveis:
            if pasta and os.path.isdir(pasta):
                try:
                    if not os.listdir(pasta):
                        os.rmdir(pasta)
                except OSError:
                    pass

    def get_bytes(self, foto):
        caminho = (foto or {}).get("storage_key", "")
        if not caminho or not os.path.exists(caminho):
            return None

        with open(caminho, "rb") as f:
            return f.read()


class SupabasePhotoStorage(PhotoStorage):
    def __init__(self, bucket: Optional[str] = None):
        self.supabase = get_supabase()
        self.bucket = bucket or get_bucket_name()

    def save_uploaded_files(self, uploaded_files, ativo_tag):
        if not uploaded_files:
            return []

        pasta_ativo = normalizar_tag_storage(ativo_tag)
        arquivos_salvos = []

        for arquivo in uploaded_files:
            extensao = os.path.splitext(arquivo.name)[1].lower()
            nome_storage = f"{pasta_ativo}/{uuid.uuid4().hex}{extensao}"

            self.supabase.storage.from_(self.bucket).upload(
                path=nome_storage,
                file=arquivo.getvalue(),
                file_options={
                    "content-type": arquivo.type or "application/octet-stream"
                }
            )

            arquivos_salvos.append({
                "id": uuid.uuid4().hex,
                "nome_original": arquivo.name,
                "mime": arquivo.type or "application/octet-stream",
                "storage_key": nome_storage
            })

        return arquivos_salvos

    def delete_many(self, fotos):
        caminhos = [
            f.get("storage_key")
            for f in (fotos or [])
            if f.get("storage_key")
        ]
        if caminhos:
            self.supabase.storage.from_(self.bucket).remove(caminhos)

    def get_bytes(self, foto):
        caminho = (foto or {}).get("storage_key", "")
        if not caminho:
            return None

        try:
            return self.supabase.storage.from_(self.bucket).download(caminho)
        except Exception:
            return None


# ==========================================================
# REPOSITÓRIO DE ATIVOS
# ==========================================================
class AssetRepository:
    def list_assets(self):
        raise NotImplementedError

    def get_asset_by_tag(self, tag):
        raise NotImplementedError

    def create_asset(self, ativo):
        raise NotImplementedError

    def update_asset(self, original_tag, ativo_atualizado):
        raise NotImplementedError

    def delete_asset(self, tag):
        raise NotImplementedError


class JsonAssetRepository(AssetRepository):
    def __init__(self, arquivo_json=ARQUIVO_ATIVOS):
        self.arquivo_json = arquivo_json

    def list_assets(self):
        return carregar_json(self.arquivo_json)

    def get_asset_by_tag(self, tag):
        tag = normalizar_tag(tag)
        return next(
            (a for a in self.list_assets() if normalizar_tag(a.get("tag", "")) == tag),
            None
        )

    def create_asset(self, ativo):
        lista = self.list_assets()
        lista.append(ativo)
        salvar_json(self.arquivo_json, lista)

    def update_asset(self, original_tag, ativo_atualizado):
        original_tag = normalizar_tag(original_tag)
        lista = self.list_assets()

        for i, ativo in enumerate(lista):
            if normalizar_tag(ativo.get("tag", "")) == original_tag:
                lista[i] = ativo_atualizado
                salvar_json(self.arquivo_json, lista)
                return True

        return False

    def delete_asset(self, tag):
        tag = normalizar_tag(tag)
        lista = self.list_assets()
        nova_lista = [a for a in lista if normalizar_tag(a.get("tag", "")) != tag]
        salvar_json(self.arquivo_json, nova_lista)
        return True


class SupabaseAssetRepository(AssetRepository):
    TABLE_NAME = "assets"

    def __init__(self):
        self.supabase = get_supabase()

    def _sanitize_asset(self, ativo: dict) -> dict:
        return {
            "tag": normalizar_tag(ativo.get("tag")),
            "tipo": str(ativo.get("tipo", "")).strip(),
            "tag_local": str(ativo.get("tag_local", "")).strip(),
            "descricao": str(ativo.get("descricao", "")).strip(),
            "pai": normalizar_tag(ativo.get("pai", "")),
            "fabricante": str(ativo.get("fabricante", "")).strip(),
            "modelo": str(ativo.get("modelo", "")).strip(),
            "observacoes": str(ativo.get("observacoes", "")).strip(),
            "local_principal": bool(ativo.get("local_principal", False)),
            "fotos": ativo.get("fotos", []) or [],
            "pdfs": ativo.get("pdfs", []) or [],
            "pecas": ativo.get("pecas", []) or [],
        }

    def list_assets(self):
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .order("tag")
            .execute()
        )
        return resp.data or []

    def get_asset_by_tag(self, tag):
        tag = normalizar_tag(tag)
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .eq("tag", tag)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create_asset(self, ativo):
        payload = self._sanitize_asset(ativo)
        self.supabase.table(self.TABLE_NAME).insert(payload).execute()

    def update_asset(self, original_tag, ativo_atualizado):
        original_tag = normalizar_tag(original_tag)
        payload = self._sanitize_asset(ativo_atualizado)

        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .update(payload)
            .eq("tag", original_tag)
            .execute()
        )

        return bool(resp.data)

    def delete_asset(self, tag):
        tag = normalizar_tag(tag)
        self.supabase.table(self.TABLE_NAME).delete().eq("tag", tag).execute()
        return True


# ==========================================================
# REPOSITÓRIO DE PEÇAS
# ==========================================================
class PartRepository:
    def list_parts(self):
        raise NotImplementedError


class JsonPartRepository(PartRepository):
    def __init__(self, arquivo_json=ARQUIVO_PECAS):
        self.arquivo_json = arquivo_json

    def list_parts(self):
        return carregar_json(self.arquivo_json)


class SupabasePartRepository(PartRepository):
    TABLE_NAME = "parts"

    def __init__(self):
        self.supabase = get_supabase()

    def list_parts(self):
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .order("codigo")
            .execute()
        )
        return resp.data or []

    def get_part_by_code(self, codigo):
        codigo = str(codigo or "").strip().upper()
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .eq("codigo", codigo)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create_part(self, peca):
        payload = {
            "codigo": str(peca.get("codigo", "")).strip().upper(),
            "descricao": str(peca.get("descricao", "")).strip().upper(),
            "referencia": str(peca.get("referencia", "")).strip().upper(),
            "fabricante": str(peca.get("fabricante", "")).strip().upper(),
            "observacoes": str(peca.get("observacoes", "")).strip(),
        }
        self.supabase.table(self.TABLE_NAME).insert(payload).execute()

    def update_part(self, codigo_original, dados_atualizados):
        codigo_original = str(codigo_original or "").strip().upper()

        payload = {
            "codigo": str(dados_atualizados.get("codigo", codigo_original)).strip().upper(),
            "descricao": str(dados_atualizados.get("descricao", "")).strip().upper(),
            "referencia": str(dados_atualizados.get("referencia", "")).strip().upper(),
            "fabricante": str(dados_atualizados.get("fabricante", "")).strip().upper(),
            "observacoes": str(dados_atualizados.get("observacoes", "")).strip(),
        }

        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .update(payload)
            .eq("codigo", codigo_original)
            .execute()
        )
        return bool(resp.data)

    def delete_part(self, codigo):
        codigo = str(codigo or "").strip().upper()
        self.supabase.table(self.TABLE_NAME).delete().eq("codigo", codigo).execute()
        return True


# ==========================================================
# ESQUELETO ANTIGO
# ==========================================================
class SqlAssetRepository(AssetRepository):
    def __init__(self, connection):
        self.connection = connection

    def list_assets(self):
        raise NotImplementedError("Implemente a leitura no seu banco.")

    def get_asset_by_tag(self, tag):
        raise NotImplementedError("Implemente a busca no seu banco.")

    def create_asset(self, ativo):
        raise NotImplementedError("Implemente o insert no seu banco.")

    def update_asset(self, original_tag, ativo_atualizado):
        raise NotImplementedError("Implemente o update no seu banco.")

    def delete_asset(self, tag):
        raise NotImplementedError("Implemente o delete no seu banco.")