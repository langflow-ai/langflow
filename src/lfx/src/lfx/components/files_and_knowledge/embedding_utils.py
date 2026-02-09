"""Shared embedding utilities used by both KnowledgeIngestionComponent and the Memories API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langflow.services.auth.utils import encrypt_api_key
from lfx.services.deps import get_settings_service

OPENAI_EMBEDDING_MODEL_NAMES = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
]
HUGGINGFACE_MODEL_NAMES = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2",
]
COHERE_MODEL_NAMES = ["embed-english-v3.0", "embed-multilingual-v3.0"]


def get_embedding_provider(embedding_model: str) -> str:
    """Get embedding provider by matching model name to known lists."""
    if embedding_model in OPENAI_EMBEDDING_MODEL_NAMES:
        return "OpenAI"
    if embedding_model in HUGGINGFACE_MODEL_NAMES:
        return "HuggingFace"
    if embedding_model in COHERE_MODEL_NAMES:
        return "Cohere"
    return "Custom"


def build_embeddings(embedding_model: str, api_key: str, chunk_size: int = 1000, provider: str | None = None):
    """Build embedding model using provider patterns."""
    if not provider:
        provider = get_embedding_provider(embedding_model)

    if provider == "OpenAI":
        from langchain_openai import OpenAIEmbeddings

        if not api_key:
            msg = "OpenAI API key is required when using OpenAI provider"
            raise ValueError(msg)
        return OpenAIEmbeddings(
            model=embedding_model,
            api_key=api_key,
            chunk_size=chunk_size,
        )
    if provider == "HuggingFace":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=embedding_model)
    if provider == "Cohere":
        from langchain_cohere import CohereEmbeddings

        if not api_key:
            msg = "Cohere API key is required when using Cohere provider"
            raise ValueError(msg)
        return CohereEmbeddings(
            model=embedding_model,
            cohere_api_key=api_key,
        )
    msg = f"Unsupported embedding provider: {provider}"
    raise ValueError(msg)


def build_embedding_metadata(
    embedding_model: str,
    api_key: str | None,
    chunk_size: int = 1000,
) -> dict[str, Any]:
    """Build embedding model metadata dict."""
    embedding_provider = get_embedding_provider(embedding_model)

    encrypted_api_key = None
    if api_key:
        settings_service = get_settings_service()
        try:
            encrypted_api_key = encrypt_api_key(api_key, settings_service=settings_service)
        except (TypeError, ValueError):
            pass

    return {
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "api_key": encrypted_api_key,
        "api_key_used": bool(api_key),
        "chunk_size": chunk_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_embedding_metadata(kb_path: Path, embedding_model: str, api_key: str) -> None:
    """Save embedding model metadata to disk."""
    embedding_metadata = build_embedding_metadata(embedding_model, api_key)
    metadata_path = kb_path / "embedding_metadata.json"
    metadata_path.write_text(json.dumps(embedding_metadata, indent=2))
