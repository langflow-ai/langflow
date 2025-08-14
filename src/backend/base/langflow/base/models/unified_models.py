from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from langflow.base.models.openai_constants import OPENAI_MODELS_DETAILED

from .google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS_DETAILED

MODELS_DETAILED = [ANTHROPIC_MODELS_DETAILED, OPENAI_MODELS_DETAILED, GOOGLE_GENERATIVE_AI_MODELS_DETAILED]


def get_unified_models_detailed(
    provider: list[str] | None = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool | None = None,
    **metadata_filters,
):
    """Return a list of providers and their models, optionally filtered.

    Parameters
    ----------
    provider : list[str] | None
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

    # Gather all models from imported *_MODELS_DETAILED lists (flatten & filter in one pass)
    provider_set = set(provider) if provider else None
    meta_keys = set(("provider", "name"))

    filtered_models: list[dict] = []
    for models_detailed in MODELS_DETAILED:
        for md in models_detailed:
            # Fastest exit if unsupported
            if (not include_unsupported) and md.get("not_supported", False):
                continue
            if provider_set is not None and md.get("provider") not in provider_set:
                continue
            if model_name is not None and md.get("name") != model_name:
                continue
            if model_type is not None and md.get("model_type") != model_type:
                continue
            # Avoid function call & loop unless metadata_filters is nonempty
            if metadata_filters:
                for k, v in metadata_filters.items():
                    if md.get(k) != v:
                        break
                else:
                    filtered_models.append(md)
                    continue
                continue
            filtered_models.append(md)

    # Fast provider grouping with dict.setdefault, skip dict-comp for each model
    provider_map: dict[str, list[dict]] = {}
    for metadata in filtered_models:
        prov = metadata.get("provider", "Unknown")
        entry = provider_map.setdefault(prov, [])
        # Use dict comprehension with fixed set for slight speedup
        entry.append(
            {
                "model_name": metadata.get("name"),
                "metadata": {k: v for k, v in metadata.items() if k not in meta_keys},
            }
        )

    return [{"provider": prov, "models": models} for prov, models in provider_map.items()]
