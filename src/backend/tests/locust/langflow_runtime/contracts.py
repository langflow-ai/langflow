"""Shared performance-suite contract constants for flows and datasets.

HITL lifecycle steps, default webhook payload, and other cross-cutting
strings referenced by ``flows/defaults``, ``flows/fixture_index``,
``datasets/registry``, validators, and unit/integration tests.
"""

from __future__ import annotations

HITL_LIFECYCLE_STEPS = [
    "background",
    "suspended",
    "pending",
    "resume",
    "completed",
]
HITL_LIFECYCLE_RULE = "->".join(HITL_LIFECYCLE_STEPS)

# Webhook POST body for the webhook stress axis.
DEFAULT_WEBHOOK_PAYLOAD = {
    "event": "perf-webhook",
    "seq": 1,
    "marker": "PERF_WEBHOOK",
}
