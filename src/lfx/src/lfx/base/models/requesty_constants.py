"""Requesty model catalog primitives.

Requesty exposes 600+ models through a unified OpenAI-compatible endpoint and
the catalog changes frequently, so the unified-models layer treats Requesty as
a live-fetched provider (see ``LIVE_MODEL_PROVIDERS`` in ``model_metadata`` and
``fetch_live_requesty_models`` in ``model_utils``).

The small seed list below is shown when the user has not yet configured a
``REQUESTY_API_KEY``. Once credentials are saved, ``replace_with_live_models``
swaps these rows for the current live catalog from
``https://router.requesty.ai/v1/models``.
"""

from .model_metadata import create_model_metadata

REQUESTY_MODELS_DETAILED = [
    create_model_metadata(
        provider="Requesty",
        name="anthropic/claude-sonnet-4-5",
        icon="Requesty",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Requesty",
        name="openai/gpt-4o",
        icon="Requesty",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Requesty",
        name="openai/gpt-4o-mini",
        icon="Requesty",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Requesty",
        name="google/gemini-2.5-flash",
        icon="Requesty",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="Requesty",
        name="deepseek/deepseek-chat",
        icon="Requesty",
        tool_calling=True,
    ),
]
