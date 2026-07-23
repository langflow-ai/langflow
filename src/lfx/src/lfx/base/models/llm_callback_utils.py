"""Shared helpers for reading model and provider from a LangChain LLM callback.

Centralizes the two pure extractions that both the native tracing callback and the
leak-safe provider-metrics callback need, so the provider heuristic has one home instead
of a copy per callback. No network, no heavy deps: just the ``invocation_params`` dict and
the model name string.
"""

from __future__ import annotations

from typing import Any


def extract_llm_model_name(kwargs: dict[str, Any]) -> str | None:
    """Extract the model name from LangChain invocation params.

    Checks ``invocation_params["model_name"]`` first (OpenAI-style), then
    ``invocation_params["model"]`` (Anthropic/generic style).

    Args:
        kwargs: The ``**kwargs`` dict passed to ``on_llm_start`` or
            ``on_chat_model_start`` by the LangChain callback system.

    Returns:
        Model name string, or ``None`` if not present.
    """
    params = kwargs.get("invocation_params") or {}
    return params.get("model_name") or params.get("model") or None


def detect_provider_from_model(model_name: str | None) -> str | None:
    """Detect provider from model name for the ``gen_ai.provider.name`` attribute.

    Pattern matching enables provider detection without database lookups or complex
    configuration, making traces and metrics self-contained and parseable by
    observability tools.
    """
    if not model_name:
        return None

    model_lower = model_name.lower()

    # Pattern-based detection works across different LangChain integrations.
    # Azure is checked before OpenAI because Azure OpenAI model names contain "gpt"
    # (e.g. "azure/gpt-4"), which would otherwise match the OpenAI branch first.
    # ponytail: name-based detection can't catch a bare "gpt-4" Azure deployment;
    # thread the provider from the component/model class if that case matters (LE-1993).
    if "azure" in model_lower:
        return "azure"
    if "gpt" in model_lower or "o1" in model_lower or model_lower.startswith("text-"):
        return "openai"
    if "claude" in model_lower:
        return "anthropic"
    if "gemini" in model_lower or "palm" in model_lower:
        return "google"
    if "llama" in model_lower:
        return "meta"
    if "mistral" in model_lower or "mixtral" in model_lower:
        return "mistral"
    if "command" in model_lower or "coral" in model_lower:
        return "cohere"
    if "titan" in model_lower or "nova" in model_lower:
        return "amazon"

    return None
