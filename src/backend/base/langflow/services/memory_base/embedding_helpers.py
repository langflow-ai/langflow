"""Embedding provider inference for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

import contextlib

# Provider inference patterns. Order matters: more specific patterns first.
# The provider names must match the keys in
# ``lfx.base.models.unified_models.class_registry.EMBEDDING_PROVIDER_CLASS_MAPPING``
# so the inferred provider can be used to instantiate the matching embedding
# class without further translation.
_MODEL_TO_PROVIDER: list[tuple[list[str], str]] = [
    # Google Generative AI uses a "models/" prefix for every embedding name.
    # Matched first so it doesn't get caught by the OpenAI "text-embedding-"
    # rule below (Google has "models/text-embedding-004").
    (
        [
            "models/gemini-embedding",
            "models/text-embedding",
            "models/embedding-",
            "gemini-embedding",
        ],
        "Google Generative AI",
    ),
    (["text-embedding-", "ada-", "gpt-"], "OpenAI"),
    (["embed-english", "embed-multilingual"], "Cohere"),
    (["sentence-transformers", "bert-", "huggingface"], "HuggingFace"),
    # Other Google models (PaLM/Gecko legacy names).
    (["palm", "gecko"], "Google Generative AI"),
    (["ollama"], "Ollama"),
    (["azure"], "Azure OpenAI"),
]


def infer_embedding_provider(embedding_model: str) -> str:
    """Derive embedding provider name from a model string.

    Looks up the model in the unified models catalog first so the answer
    matches what the UI dropdown shows; falls back to pattern-based
    inference for legacy/edge cases.
    """
    if not embedding_model:
        return "OpenAI"  # Safe default — matches _resolve_embedding fallback

    catalog_provider = _lookup_provider_in_catalog(embedding_model)
    if catalog_provider:
        return catalog_provider

    lower = embedding_model.lower()
    for patterns, provider in _MODEL_TO_PROVIDER:
        if any(p in lower for p in patterns):
            return provider
    return "OpenAI"  # Safe default — matches _resolve_embedding fallback


def infer_llm_provider(model_name: str) -> str:
    """Derive LLM provider name from a chat-model string.

    Looks the model up in the unified model catalog
    (``get_provider_for_model_name``) — the same registry every other
    provider-aware component uses, populated from each provider's
    ``*_constants.py``. This keeps preproc_model lookup consistent with
    the rest of the platform and avoids a hand-maintained pattern map.

    Raises ``ValueError`` if the catalog has no matching entry. Unlike the
    embedding fallback (where OpenAI is a near-universal default), an
    unknown LLM name is genuinely ambiguous: a silent OpenAI fallback would
    hand the user a confusing API-key error from the wrong provider when
    what they actually have is a typo or an unregistered fine-tune.
    """
    from lfx.base.models.unified_models import get_provider_for_model_name

    if not model_name:
        msg = "preproc_model is required when preprocessing is enabled"
        raise ValueError(msg)
    provider = get_provider_for_model_name(model_name)
    if not provider:
        msg = (
            f"Unknown LLM model '{model_name}' — provider could not be inferred. "
            "Configure a model that is registered in the unified model catalog."
        )
        raise ValueError(msg)
    return provider


def _lookup_provider_in_catalog(embedding_model: str) -> str | None:
    """Return the provider for ``embedding_model`` from the unified catalog, if known."""
    with contextlib.suppress(Exception):
        # Imported lazily so the helper has no hard dependency on the
        # unified_models package at import time (keeps test imports cheap).
        from lfx.base.models.unified_models.model_catalog import get_unified_models_detailed

        all_providers = get_unified_models_detailed(
            model_type="embeddings",
            include_deprecated=True,
            include_unsupported=True,
        )
        for provider_data in all_providers:
            for model_data in provider_data.get("models", []):
                if model_data.get("model_name") == embedding_model:
                    return provider_data.get("provider")
    return None
