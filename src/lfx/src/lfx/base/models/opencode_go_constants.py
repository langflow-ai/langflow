"""OpenCode Go model catalog primitives.

OpenCode Go (the "Go" tier of OpenCode Zen) proxies a large, frequently changing
set of models through one OpenAI-compatible endpoint, so the unified-models layer
treats it as a live-fetched provider (see ``LIVE_MODEL_PROVIDERS`` in
``model_metadata`` and ``fetch_live_opencode_go_models`` in ``model_utils``).

The small seed list below is shown only while the user has not yet configured an
``OPENCODE_GO_API_KEY``. Once credentials are saved, ``replace_with_live_models``
swaps these rows wholesale for the live catalog from
``https://opencode.ai/zen/go/v1/models``.

These IDs are bare names that also exist in the Anthropic/OpenAI catalogs, so this
list is registered LAST in ``_STATIC_MODELS_DETAILED``; ``get_provider_for_model_name``
returns the first hit, which keeps those names resolving to their original provider.
"""

from .model_metadata import create_model_metadata

# Seed IDs are a conservative subset of the published OpenCode Zen catalog
# (https://opencode.ai/docs/zen/). Verified against the live Go ``/models``
# endpoint when a Go subscription key is available; the live catalog overrides
# this seed at runtime.
_SEED_MODEL_NAMES = (
    "claude-sonnet-5",
    "claude-haiku-4.5",
    "gpt-5.2",
    "gemini-3-flash",
    "qwen3-coder",
)

OPENCODE_GO_MODELS_DETAILED = [
    create_model_metadata(
        provider="OpenCode Go",
        name=name,
        icon="Terminal",
        tool_calling=True,
    )
    for name in _SEED_MODEL_NAMES
]
