"""OpenRouter model catalog primitives.

OpenRouter exposes 300+ models through a unified OpenAI-compatible endpoint and
the catalog changes frequently, so the unified-models layer treats OpenRouter as
a live-fetched provider (see ``LIVE_MODEL_PROVIDERS`` in ``model_metadata`` and
``fetch_live_openrouter_models`` in ``model_utils``).

The small seed list below is shown when the user has not yet configured an
``OPENROUTER_API_KEY``. Once credentials are saved, ``replace_with_live_models``
swaps these rows for the current live catalog from
``https://openrouter.ai/api/v1/models``.
"""

from .model_metadata import create_model_metadata

OPENROUTER_MODELS_DETAILED = [
    create_model_metadata(
        provider="OpenRouter",
        name="anthropic/claude-opus-4.7",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="anthropic/claude-sonnet-4.5",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="anthropic/claude-haiku-4.5",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="openai/gpt-4o",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="openai/gpt-4o-mini",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="google/gemini-2.5-pro",
        icon="OpenRouter",
        tool_calling=True,
    ),
    create_model_metadata(
        provider="OpenRouter",
        name="meta-llama/llama-3.3-70b-instruct",
        icon="OpenRouter",
        tool_calling=True,
    ),
]
