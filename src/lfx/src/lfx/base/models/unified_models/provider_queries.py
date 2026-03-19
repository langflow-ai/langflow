"""Provider metadata accessors and static model catalog primitives."""

from __future__ import annotations

from functools import lru_cache

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from lfx.base.models.google_generative_ai_constants import (
    GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED,
    GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
)
from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA
from lfx.base.models.ollama_constants import (
    OLLAMA_EMBEDDING_MODELS_DETAILED,
    OLLAMA_MODELS_DETAILED,
)
from lfx.base.models.openai_constants import (
    OPENAI_EMBEDDING_MODELS_DETAILED,
    OPENAI_MODELS_DETAILED,
)
from lfx.base.models.watsonx_constants import WATSONX_MODELS_DETAILED


@lru_cache(maxsize=1)
def get_model_provider_metadata() -> dict:
    """Return the model provider metadata configuration."""
    return MODEL_PROVIDER_METADATA


model_provider_metadata = get_model_provider_metadata()


@lru_cache(maxsize=1)
def get_models_detailed() -> list[list[dict]]:
    """Return grouped static model metadata from provider constants."""
    return [
        ANTHROPIC_MODELS_DETAILED,
        OPENAI_MODELS_DETAILED,
        OPENAI_EMBEDDING_MODELS_DETAILED,
        GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
        GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED,
        OLLAMA_MODELS_DETAILED,
        OLLAMA_EMBEDDING_MODELS_DETAILED,
        WATSONX_MODELS_DETAILED,
    ]


MODELS_DETAILED = get_models_detailed()


@lru_cache(maxsize=1)
def get_model_provider_variable_mapping() -> dict[str, str]:
    """Return primary (first required secret) variable for each provider.

    Backward-compatible helper used in many callers that still expect a single
    provider-level variable key.
    """
    result = {}
    for provider, meta in model_provider_metadata.items():
        for var in meta.get("variables", []):
            if var.get("required") and var.get("is_secret"):
                result[provider] = var["variable_key"]
                break
        # Fallback to first variable if no required secret found
        if provider not in result and meta.get("variables"):
            result[provider] = meta["variables"][0]["variable_key"]
    return result


def get_provider_all_variables(provider: str) -> list[dict]:
    """Get all variables for a provider."""
    meta = model_provider_metadata.get(provider, {})
    return meta.get("variables", [])


def get_provider_required_variable_keys(provider: str) -> list[str]:
    """Get all required variable keys for a provider."""
    variables = get_provider_all_variables(provider)
    return [v["variable_key"] for v in variables if v.get("required")]


@lru_cache(maxsize=1)
def _get_all_provider_specific_field_names() -> set[str]:
    """Return set of all field names used as mapping_field by any provider."""
    names: set[str] = set()
    for meta in model_provider_metadata.values():
        for v in meta.get("variables", []):
            mapping = v.get("component_metadata", {}).get("mapping_field")
            if mapping:
                names.add(mapping)
    return names


def get_model_providers() -> list[str]:
    """Return a sorted list of unique provider names."""
    return sorted({md.get("provider", "Unknown") for group in MODELS_DETAILED for md in group})


def get_provider_from_variable_key(variable_key: str) -> str | None:
    """Get provider name from a variable key.

    Args:
        variable_key: The variable key (e.g., "OPENAI_API_KEY", "WATSONX_APIKEY")

    Returns:
        The provider name or None if not found
    """
    for provider, meta in model_provider_metadata.items():
        for var in meta.get("variables", []):
            if var.get("variable_key") == variable_key:
                return provider
    return None
