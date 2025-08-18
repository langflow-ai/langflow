from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from langflow.base.models.openai_constants import OPENAI_MODELS_DETAILED

from .google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS_DETAILED

MODELS_DETAILED = [ANTHROPIC_MODELS_DETAILED, OPENAI_MODELS_DETAILED, GOOGLE_GENERATIVE_AI_MODELS_DETAILED]


def get_model_providers() -> list[str]:
    """Return a sorted list of unique provider names."""
    return sorted({md.get("provider", "Unknown") for group in MODELS_DETAILED for md in group})


def get_unified_models_detailed(
    providers: list[str] | None = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool | None = None,
    **metadata_filters,
):
    """Return a list of providers and their models, optionally filtered.

    Parameters
    ----------
    providers : list[str] | None
        If given, only models from these providers are returned.
    model_name : str | None
        If given, only the model with this exact name is returned.
    model_type : str | None
        Optional. Restrict to models whose metadata "model_type" matches this value.
    include_unsupported : bool
        When False (default) models whose metadata contains ``not_supported=True``
        are filtered out.
    **metadata_filters
        Arbitrary key/value pairs to match against the model's metadata.
        Example: ``get_unified_models_detailed(size="4k", context_window=8192)``

    Notes:
    • Filtering is exact-match on the metadata values.
    • If you *do* want to see unsupported models set ``include_unsupported=True``.
    """
    if include_unsupported is None:
        include_unsupported = False

    # Gather all models from imported *_MODELS_DETAILED lists
    all_models: list[dict] = []
    for models_detailed in MODELS_DETAILED:
        all_models.extend(models_detailed)

    # Apply filters
    filtered_models: list[dict] = []
    for md in all_models:
        # Skip models flagged as not_supported unless explicitly included
        if (not include_unsupported) and md.get("not_supported", False):
            continue

        if providers and md.get("provider") not in providers:
            continue
        if model_name and md.get("name") != model_name:
            continue
        if model_type and md.get("model_type") != model_type:
            continue
        # Match arbitrary metadata key/value pairs
        if any(md.get(k) != v for k, v in metadata_filters.items()):
            continue

        filtered_models.append(md)

    # Group by provider
    provider_map: dict[str, list[dict]] = {}
    for metadata in filtered_models:
        prov = metadata.get("provider", "Unknown")
        provider_map.setdefault(prov, []).append(
            {
                "model_name": metadata.get("name"),
                "metadata": {k: v for k, v in metadata.items() if k not in ("provider", "name")},
            }
        )

    # Format as requested
    return [{"provider": prov, "models": models} for prov, models in provider_map.items()]
