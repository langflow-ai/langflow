"""Backend label resolution for background-execution metrics.

Throughput/outcome/duration metrics are DB-derived in the API-side collector
(``metrics_collector.py``); the runner/sweep emit no in-process counters.
``current_backend()`` supplies the ``backend`` label every collected series carries.
"""

from __future__ import annotations


def current_backend() -> str:
    """Best-effort: 'scaled' when a scaled backend is wired, else 'default'. Never raises.

    Asks the service which backend it built rather than reading
    ``background_backend_is_scaled``. That setting only says a scaled backend was
    requested (``job_queue_type=redis`` here), and a request whose scaled modules are
    unavailable degrades to the in-process executor, whose jobs are not scaled.
    """
    try:
        from langflow.services.deps import get_background_execution_service

        return "scaled" if get_background_execution_service().is_scaled else "default"
    except Exception:  # noqa: BLE001
        return "default"
