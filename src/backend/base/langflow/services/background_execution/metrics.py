"""Backend label resolution for background-execution structured logs.

Throughput/outcome/duration metrics are DB-derived in the API-side collector
(``metrics_collector.py``); the runner/sweep no longer emit in-process counters.
Only ``current_backend()`` remains: the structured ``event_type="bg_job"`` logs
tag each line with the backend this run executes on.
"""

from __future__ import annotations


def current_backend() -> str:
    """Best-effort: 'scaled' when the redis job queue is active, else 'default'. Never raises."""
    try:
        from langflow.services.deps import get_settings_service

        return "scaled" if get_settings_service().settings.background_backend_is_scaled else "default"
    except Exception:  # noqa: BLE001
        return "default"
