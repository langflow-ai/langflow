"""Provider metadata accessors and static model catalog primitives."""

from __future__ import annotations

from functools import lru_cache

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from lfx.base.models.azure_ai_foundry_constants import AZURE_AI_FOUNDRY_MODELS_DETAILED
from lfx.base.models.google_generative_ai_constants import (
    GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED,
    GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
)
from lfx.base.models.model_metadata import (
    CONDITIONAL_LIVE_MODEL_PROVIDERS,
    LIVE_MODEL_PROVIDERS,
    MODEL_PROVIDER_METADATA,
)
from lfx.base.models.ollama_constants import (
    OLLAMA_EMBEDDING_MODELS_DETAILED,
    OLLAMA_MODELS_DETAILED,
)
from lfx.base.models.openai_constants import (
    OPENAI_EMBEDDING_MODELS_DETAILED,
    OPENAI_MODELS_DETAILED,
)
from lfx.base.models.openrouter_constants import OPENROUTER_MODELS_DETAILED
from lfx.base.models.orcarouter_constants import ORCAROUTER_MODELS_DETAILED
from lfx.base.models.watsonx_constants import WATSONX_MODELS_DETAILED


@lru_cache(maxsize=1)
def get_model_provider_metadata() -> dict:
    """Return the model provider metadata configuration."""
    return MODEL_PROVIDER_METADATA


model_provider_metadata = get_model_provider_metadata()


_STATIC_MODELS_DETAILED: list[list[dict]] = [
    ANTHROPIC_MODELS_DETAILED,
    OPENAI_MODELS_DETAILED,
    OPENAI_EMBEDDING_MODELS_DETAILED,
    GOOGLE_GENERATIVE_AI_MODELS_DETAILED,
    GOOGLE_GENERATIVE_AI_EMBEDDING_MODELS_DETAILED,
    OLLAMA_MODELS_DETAILED,
    OLLAMA_EMBEDDING_MODELS_DETAILED,
    OPENROUTER_MODELS_DETAILED,
    ORCAROUTER_MODELS_DETAILED,
    WATSONX_MODELS_DETAILED,
    # Last: seed deployment aliases (gpt-4o, gpt-4.1, …) overlap OpenAI rows.
    # ``get_provider_for_model_name`` returns the first catalog hit, so keep
    # Foundry after established providers for 1.8.x backwards compat.
    AZURE_AI_FOUNDRY_MODELS_DETAILED,
]


@lru_cache(maxsize=1)
def get_models_detailed() -> list[list[dict]]:
    """Return grouped model metadata, preferring the models.dev override.

    When ``lfx.base.models.models_dev_catalog`` has an active snapshot
    installed (loaded from disk or fetched from models.dev at startup),
    apply its overrides on top of the bundled static lists. Providers the
    snapshot doesn't cover keep their bundled rows; live-fetched providers
    (Ollama, IBM WatsonX, OpenRouter) keep theirs too because
    ``replace_with_live_models`` overrides at read time, downstream of this
    function. ``get_models_detailed.cache_clear()`` must be called whenever
    a new snapshot is installed.
    """
    # Lazy import to avoid a circular dependency on application startup
    # (models_dev_catalog imports from this module transitively via
    # invalidate_catalog_cache).
    from lfx.base.models.models_dev_catalog import apply_models_dev_overrides, get_active_snapshot

    snapshot = get_active_snapshot()
    if snapshot is None:
        return _STATIC_MODELS_DETAILED
    return apply_models_dev_overrides(_STATIC_MODELS_DETAILED, snapshot)


# NOTE: ``MODELS_DETAILED`` is a back-compat binding for callers that imported
# it before ``get_models_detailed()`` existed. It reflects the **static**
# baseline only — once a models.dev snapshot installs at startup, in-process
# consumers must call ``get_models_detailed()`` (which honours the override and
# benefits from ``cache_clear()``) to see fresh data.
MODELS_DETAILED = _STATIC_MODELS_DETAILED


@lru_cache(maxsize=1)
def get_model_provider_variable_mapping() -> dict[str, str]:
    """Return primary (first required secret) variable for each provider.

    Backward-compatible helper used in many callers that still expect a single
    provider-level variable key.
    """
    result = {}
    for provider, meta in model_provider_metadata.items():
        variables = meta.get("variables", [])
        # Prefer a required secret (the canonical API key); then any secret
        # (an *optional* API key, e.g. a local OpenAI-compatible server like
        # vLLM whose VLLM_API_KEY is optional); only then fall back to the first
        # variable. Without the "any secret" step the mapping would point at the
        # first required *non-secret* connection field (e.g. a base URL), which
        # get_api_key_for_provider would then resolve and send as the API key.
        chosen = next((v["variable_key"] for v in variables if v.get("required") and v.get("is_secret")), None)
        if chosen is None:
            chosen = next((v["variable_key"] for v in variables if v.get("is_secret")), None)
        if chosen is None and variables:
            chosen = variables[0]["variable_key"]
        if chosen is not None:
            result[provider] = chosen
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
    """Return a sorted list of unique provider names.

    Unions providers that have a static model catalog (``get_models_detailed``)
    with every provider declared in ``MODEL_PROVIDER_METADATA``. The latter
    covers providers that ship no static catalog and rely entirely on live
    discovery -- including providers contributed by extension bundles via
    ``provider_registry`` (which merge their metadata in place).
    """
    providers = {md.get("provider", "Unknown") for group in get_models_detailed() for md in group}
    providers.update(model_provider_metadata.keys())
    return sorted(providers)


def get_live_only_providers() -> list[str]:
    """Return providers whose models come exclusively from live discovery.

    A provider qualifies when it is declared in the provider metadata and in
    the live-discovery gates but ships no static catalog rows -- today always
    a provider contributed by an extension bundle via ``provider_registry``
    (e.g. vLLM, OpenAI Compatible). Catalog-driven listings such as
    ``get_unified_models_detailed`` can never emit these, and
    ``replace_with_live_models`` only appends a provider once it is configured
    *and* its endpoint returns models, so provider-facing surfaces (the Model
    Providers dialog) must union them in explicitly or an unconfigured
    provider would be undiscoverable.

    Metadata-only providers that are *not* live-capable (Azure OpenAI, Groq)
    are deliberately excluded: with neither a catalog nor live discovery they
    could never list models, and they are intentionally absent from the
    unified-model UI today.

    Not cached: ``register_provider`` mutates the metadata and live gates in
    place, and the underlying collections are small.
    """
    cataloged = {md.get("provider") for group in get_models_detailed() for md in group}
    live_capable = {*LIVE_MODEL_PROVIDERS, *CONDITIONAL_LIVE_MODEL_PROVIDERS}
    return sorted(name for name in model_provider_metadata if name in live_capable and name not in cataloged)


def get_provider_for_model_name(model_name: str) -> str:
    """Return the provider for a model name by searching the active catalog.

    Retained for backwards compatibility with components authored against the
    pre-refactor ``unified_models`` module (e.g. flows exported from 1.8.x).
    """
    if not model_name or not isinstance(model_name, str):
        return ""
    for group in get_models_detailed():
        for md in group:
            if md.get("name") == model_name:
                return md.get("provider", "") or ""
    return ""


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
