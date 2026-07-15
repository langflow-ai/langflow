"""OrcaRouter model catalog primitives.

OrcaRouter exposes many models from multiple providers through a unified
OpenAI-compatible endpoint and the catalog changes over time, so the
unified-models layer treats OrcaRouter as a live-fetched provider (see
``LIVE_MODEL_PROVIDERS`` in ``model_metadata`` and
``fetch_live_orcarouter_models`` in ``model_utils``).

The small seed list below is shown when the user has not yet configured an
``ORCAROUTER_API_KEY``. Once credentials are saved, ``replace_with_live_models``
swaps these rows for the current live catalog from
``https://api.orcarouter.ai/v1/models``. ``orcarouter/auto`` is OrcaRouter's
virtual adaptive router (a routing endpoint, not a catalog entry), so it is not
returned by ``/v1/models`` and is preserved from this seed list.
"""

from .model_metadata import create_model_metadata

ORCAROUTER_MODELS_DETAILED = [
    create_model_metadata(
        provider="OrcaRouter",
        name="orcarouter/auto",
        icon="OrcaRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OrcaRouter",
        name="openai/gpt-5.5",
        icon="OrcaRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OrcaRouter",
        name="anthropic/claude-opus-4.8",
        icon="OrcaRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OrcaRouter",
        name="google/gemini-3.5-flash",
        icon="OrcaRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OrcaRouter",
        name="deepseek/deepseek-v4-pro",
        icon="OrcaRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OrcaRouter",
        name="grok/grok-4.3",
        icon="OrcaRouter",
        tool_calling=True,
    ),
]
