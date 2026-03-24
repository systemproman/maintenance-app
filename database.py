# database.py
import os
import re
import json
import uuid
from typing import Optional

import streamlit as st
from supabase import create_client, Client


# ==========================================================
# 🔑 SUPABASE CACHE (CRÍTICO)
# ==========================================================
@st.cache_resource
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY não configurados.")

    return create_client(url, key)


def get_bucket_name() -> str:
    return os.environ.get("SUPABASE_BUCKET") or st.secrets.get("SUPABASE_BUCKET", "ativos")


# ==========================================================
# 🧠 CACHE GLOBAL DE DADOS
# ==========================================================
@st.cache_data(ttl=120)
def cache_assets():
    supabase = get_supabase()
    resp = supabase.table("assets").select("*").order("tag").execute()
    return resp.data or []


@st.cache_data(ttl=120)
def cache_parts():
    supabase = get_supabase()
    resp = supabase.table("parts").select("*").order("codigo").execute()
    return resp.data or []


def limpar_cache():
    st.cache_data.clear()


# ==========================================================
# UTILITÁRIOS
# ==========================================================
def normalizar_tag(valor):
    return str(valor or "").strip().upper()


def normalizar_tag_storage(valor):
    tag = normalizar_tag(valor)
    tag = re.sub(r"[^A-Z0-9._-]+", "_", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    return tag or "SEM_TAG"


# ==========================================================
# STORAGE
# ==========================================================
class SupabasePhotoStorage:
    def __init__(self, bucket: Optional[str] = None):
        self.supabase = get_supabase()
        self.bucket = bucket or get_bucket_name()

    def save_uploaded_files(self, uploaded_files, ativo_tag):
        if not uploaded_files:
            return []

        pasta = normalizar_tag_storage(ativo_tag)
        arquivos = []

        for arquivo in uploaded_files:
            ext = os.path.splitext(arquivo.name)[1].lower()
            nome = f"{pasta}/{uuid.uuid4().hex}{ext}"

            self.supabase.storage.from_(self.bucket).upload(
                path=nome,
                file=arquivo.getvalue(),
                file_options={"content-type": arquivo.type or "application/octet-stream"}
            )

            arquivos.append({
                "id": uuid.uuid4().hex,
                "nome_original": arquivo.name,
                "mime": arquivo.type or "application/octet-stream",
                "storage_key": nome
            })

        return arquivos

    def delete_many(self, fotos):
        caminhos = [f.get("storage_key") for f in fotos or [] if f.get("storage_key")]
        if caminhos:
            self.supabase.storage.from_(self.bucket).remove(caminhos)

    @st.cache_data(ttl=600)
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

    def list_assets(self):
        return cache_assets()

    def get_asset_by_tag(self, tag):
        tag = normalizar_tag(tag)
        return next(
            (a for a in cache_assets() if normalizar_tag(a.get("tag")) == tag),
            None
        )

    def create_asset(self, ativo):
        get_supabase().table("assets").insert(ativo).execute()
        limpar_cache()

    def update_asset(self, tag, ativo):
        get_supabase().table("assets").update(ativo).eq("tag", normalizar_tag(tag)).execute()
        limpar_cache()

    def delete_asset(self, tag):
        get_supabase().table("assets").delete().eq("tag", normalizar_tag(tag)).execute()
        limpar_cache()


# ==========================================================
# REPOSITÓRIO DE PEÇAS
# ==========================================================
class SupabasePartRepository:

    def list_parts(self):
        return cache_parts()

    def create_part(self, part):
        get_supabase().table("parts").insert(part).execute()
        limpar_cache()

    def update_part(self, codigo, dados):
        get_supabase().table("parts").update(dados).eq("codigo", codigo).execute()
        limpar_cache()

    def delete_part(self, codigo):
        get_supabase().table("parts").delete().eq("codigo", codigo).execute()
        limpar_cache()

    def get_part_by_code(self, codigo):
        return next(
            (p for p in cache_parts() if p.get("codigo") == codigo),
            None
        )
