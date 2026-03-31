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
