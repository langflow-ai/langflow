"""OpenCode Go model catalog primitives.

OpenCode Go (the "Go" tier of OpenCode Zen) proxies a large, frequently changing
set of models through one OpenAI-compatible endpoint, so the unified-models layer
treats it as a live-fetched provider (see ``LIVE_MODEL_PROVIDERS`` in
``model_metadata`` and ``fetch_live_opencode_go_models`` in ``model_utils``).

The small seed list below is shown only while the user has not yet configured an
``OPENCODE_GO_API_KEY``. Once credentials are saved, ``replace_with_live_models``
swaps these rows wholesale for the live catalog from
``https://opencode.ai/zen/go/v1/models``.

OpenCode Go exposes models under short, unprefixed IDs (``kimi-k3``, ``glm-5.3``)
rather than the ``vendor/model`` form OpenRouter uses. Nothing stops such a name
from colliding with an entry in another provider's catalog — and the live endpoint
can introduce new names at any time — so this list is registered LAST in
``_STATIC_MODELS_DETAILED``. ``get_provider_for_model_name`` returns the first hit,
which keeps any shared name resolving to the provider a flow was saved with.
"""

from .model_metadata import create_model_metadata

# Verified against the live ``https://opencode.ai/zen/go/v1/models`` endpoint with
# a Go subscription: a flagship spread across the vendors the Go tier actually
# curates. The published OpenCode Zen catalog (https://opencode.ai/docs/zen/) is
# NOT a reliable source for these — it lists models the Go endpoint does not serve.
# This seed is only shown before an API key is configured; once one is saved,
# ``replace_with_live_models`` swaps it wholesale for the live catalog.
_SEED_MODEL_NAMES = (
    "deepseek-v4-pro",
    "glm-5.3",
    "kimi-k3",
    "minimax-m3",
    "qwen3.8-max",
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
