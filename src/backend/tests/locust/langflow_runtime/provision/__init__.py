"""Idempotent HTTP provisioning for the performance suite."""

from __future__ import annotations

STATE_SCHEMA_VERSION = 1
DEFAULT_ENV_ID = "perf-local"
SMOKE_FLOW_IDS = (
    "perf_passthrough",
    "perf_webhook_passthrough",
    "human_input_flow",
    "MemoryChatbotNoLLM",
)

# Full-song V1 set: every axis + Natural dual-mode fixture; excludes deferred mega-graphs.
DEFERRED_FLOW_IDS = frozenset(
    {
        "perf_ensemble_journey",
        "perf_ensemble_journey_hitl",
    }
)

__all__ = [
    "DEFAULT_ENV_ID",
    "DEFERRED_FLOW_IDS",
    "SMOKE_FLOW_IDS",
    "STATE_SCHEMA_VERSION",
]
