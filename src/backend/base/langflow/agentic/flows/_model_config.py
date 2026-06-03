"""Shared model configuration builder for agentic flows.

Extracted from translation_flow.py so that multiple flows (translation,
flow generation, Q&A) can reuse the same model config construction logic
without duplication.
"""

from __future__ import annotations


def build_model_config(provider: str, model_name: str) -> list[dict]:
    """Build model configuration for LanguageModelComponent.

    Args:
        provider: Model provider name (e.g., "OpenAI", "Anthropic").
        model_name: Model name (e.g., "gpt-4o-mini", "claude-3-5-sonnet-20241022").

    Returns:
        List containing the model config dict expected by LanguageModelComponent.
    """
    from lfx.base.models.model_metadata import get_provider_param_mapping

    param_mapping = get_provider_param_mapping(provider)
    metadata: dict = {
        "api_key_param": param_mapping.get("api_key_param", "api_key"),
        "context_length": 128000,
        "model_class": param_mapping.get("model_class", "ChatOpenAI"),
        "model_name_param": param_mapping.get("model_name_param", "model"),
    }
    # Include extra params like base_url_param for providers like Ollama
    for extra_param in ("url_param", "project_id_param", "base_url_param"):
        if extra_param in param_mapping:
            metadata[extra_param] = param_mapping[extra_param]

    return [
        {
            "icon": provider,
            "metadata": metadata,
            "name": model_name,
            "provider": provider,
        }
    ]
