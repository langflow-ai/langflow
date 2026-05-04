"""Embedding provider inference for MemoryBase.

Extracted from MemoryBaseService to keep single-responsibility per file.
"""

from __future__ import annotations

# Provider inference map — mirrors provider_patterns in KBAnalysisHelper._detect_embedding_provider
# so we can derive the provider from a model name string without filesystem access.
_MODEL_TO_PROVIDER: list[tuple[list[str], str]] = [
    (["text-embedding", "ada-", "gpt-"], "OpenAI"),
    (["embed-english", "embed-multilingual"], "Cohere"),
    (["sentence-transformers", "bert-", "huggingface"], "HuggingFace"),
    (["palm", "gecko", "google"], "Google"),
    (["ollama"], "Ollama"),
    (["azure"], "Azure OpenAI"),
]


def infer_embedding_provider(embedding_model: str) -> str:
    """Derive embedding provider name from a model string."""
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
