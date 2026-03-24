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
# 🔑 SUPABASE CONFIG (CORRIGIDO)
# ==========================================================
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY não configurados.")

    return create_client(url, key)


def get_bucket_name() -> str:
    return os.environ.get("SUPABASE_BUCKET") or st.secrets.get("SUPABASE_BUCKET", "ativos")


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

    tag = re.sub(r"[^A-Z0-9._-]+", "_", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")

    if not tag:
        tag = "SEM_TAG"

    return tag


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
class SupabaseAssetRepository:
    TABLE_NAME = "assets"

    def __init__(self):
        self.supabase = get_supabase()

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
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .eq("tag", normalizar_tag(tag))
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def create_asset(self, ativo):
        self.supabase.table(self.TABLE_NAME).insert(ativo).execute()

    def update_asset(self, tag, ativo):
        self.supabase.table(self.TABLE_NAME).update(ativo).eq("tag", normalizar_tag(tag)).execute()

    def delete_asset(self, tag):
        self.supabase.table(self.TABLE_NAME).delete().eq("tag", normalizar_tag(tag)).execute()


# ==========================================================
# REPOSITÓRIO DE PEÇAS
# ==========================================================
class SupabasePartRepository:
    TABLE_NAME = "parts"

    def __init__(self):
        self.supabase = get_supabase()

    def list_parts(self):
        resp = self.supabase.table(self.TABLE_NAME).select("*").order("codigo").execute()
        return resp.data or []

    def create_part(self, part):
        self.supabase.table(self.TABLE_NAME).insert(part).execute()

    def update_part(self, codigo, dados):
        self.supabase.table(self.TABLE_NAME).update(dados).eq("codigo", codigo).execute()

    def delete_part(self, codigo):
        self.supabase.table(self.TABLE_NAME).delete().eq("codigo", codigo).execute()

    def get_part_by_code(self, codigo):
        resp = (
            self.supabase
            .table(self.TABLE_NAME)
            .select("*")
            .eq("codigo", codigo)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
