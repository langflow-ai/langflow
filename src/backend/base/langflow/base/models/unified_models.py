from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
from langflow.base.models.openai_constants import OPENAI_MODELS_DETAILED

from .google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS_DETAILED

MODELS_DETAILED = [ANTHROPIC_MODELS_DETAILED, OPENAI_MODELS_DETAILED, GOOGLE_GENERATIVE_AI_MODELS_DETAILED]


def get_unified_models_detailed(
    provider: str | None = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool | None = None,
    **metadata_filters,
):
    """Return a list of providers and their models, optionally filtered.

    Parameters
    ----------
    provider : str | None
        If given, only models from this provider are returned.
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

    # Prepare filter items as tuple for speed
    filter_items = metadata_filters.items()
    provider_map: dict[str, list[dict]] = {}

    for models_detailed in MODELS_DETAILED:
        for md in models_detailed:
            # Fast path: skip unsupported if not included
            if not include_unsupported and md.get("not_supported", False):
                continue

            prov = md.get("provider")
            name = md.get("name")
            mtype = md.get("model_type")

            if provider is not None and prov != provider:
                continue
            if model_name is not None and name != model_name:
                continue
            if model_type is not None and mtype != model_type:
                continue

            # Fast all() for metadata filters
            if filter_items:
                for k, v in filter_items:
                    if md.get(k) != v:
                        break
                else:
                    # all matched
                    # Move model below
                    metadata = md.copy()
                    metadata.pop("provider", None)
                    metadata.pop("name", None)
                    provider_map.setdefault(prov or "Unknown", []).append({"model_name": name, "metadata": metadata})
                    continue  # model handled
                continue  # failed metadata filter

            # If no metadata_filters, just proceed
            metadata = md.copy()
            metadata.pop("provider", None)
            metadata.pop("name", None)
            provider_map.setdefault(prov or "Unknown", []).append({"model_name": name, "metadata": metadata})

    # Format as requested
    return [{"provider": prov, "models": models} for prov, models in provider_map.items()]
