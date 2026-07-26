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

__all__ = [
    "DEFAULT_ENV_ID",
    "SMOKE_FLOW_IDS",
    "STATE_SCHEMA_VERSION",
]
