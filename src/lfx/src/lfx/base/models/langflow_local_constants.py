"""Constants describing the curated "Langflow Model" provider — the bundled local LLM.

Single source of truth for the provider name, the curated model list, the SSRF allowlist,
and related metadata. Referenced from provider_queries, model_metadata, and the upcoming
local-model setup wizard. Keeping these in one module prevents drift between the three
sites that must agree (see test_langflow_local_provider_registration).
"""

from __future__ import annotations

from .model_metadata import create_model_metadata

LANGFLOW_LOCAL_PROVIDER_NAME: str = "Langflow Model"

# Why qwen2.5:1.5b: ~1GB Q4 quantized, real tool calling support, smallest viable
# model for the Agent component to function out-of-the-box. See PLAN doc §3.1.
LANGFLOW_LOCAL_DEFAULT_MODEL: str = "qwen2.5:1.5b"

LANGFLOW_LOCAL_MODELS_DETAILED: list[dict] = [
    # Why a single curated model: keeps the on-disk footprint small (~1GB) and
    # avoids confusing new users with options that all need to be pulled separately.
    # Advanced users can still use Ollama directly for any other model.
    create_model_metadata(
        provider=LANGFLOW_LOCAL_PROVIDER_NAME,
        name="qwen2.5:1.5b",
        icon="Langflow",
        tool_calling=True,
        default=True,
    ),
]

# SSRF guard: ChatLangflowLocal must reject base_urls outside this whitelist.
# Why frozenset: O(1) membership test on every __init__, plus protection against
# accidental runtime mutation that could widen the allowlist.
ALLOWED_BASE_URLS: frozenset[str] = frozenset(
    {
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        # Why host.docker.internal: when Langflow runs inside a container, Ollama
        # on the host is reached via this hostname (Docker Desktop on macOS/Windows,
        # and via --add-host on Linux). Mandatory for Docker support.
        "http://host.docker.internal:11434",
    }
)

# Anti-injection: only models in this set may be instantiated via ChatLangflowLocal.
# Derived from LANGFLOW_LOCAL_MODELS_DETAILED so the two cannot drift.
CURATED_MODEL_NAMES: frozenset[str] = frozenset(m["name"] for m in LANGFLOW_LOCAL_MODELS_DETAILED)
