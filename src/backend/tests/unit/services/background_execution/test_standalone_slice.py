"""LE-1439 guards: the kept background-execution slice is standalone.

The scaled-backend seam (``_build_scaled_backend`` / ``select_background_backend``)
ships upstream since release-1.11.0, but its modules (worker / redis_backend) do
not exist on this branch — so the functional contract is: requesting
``LANGFLOW_JOB_QUEUE_TYPE=redis`` must degrade to the in-process executor
instead of crashing on a missing import.

``metrics`` and ``metrics_collector`` used to be held here too. LE-1439 held them "by
transitivity": their base was the scaled-fleet branch, and the roster, the worker CLI wiring
and the fleet dashboard all assumed that fleet existed. The job metrics were extracted away
from all three, so the transitivity that justified holding them is gone and they now ship.
What stayed behind is what genuinely needs the fleet: ``worker_registry`` and the worker
gauges that read it.

LE-1439 anticipated this, recording that promoting the redis-independent parts of that slice
was "a separate future ticket". Both bugs it listed as known-but-held are already fixed: the
collector's run-row double count (see ``_has_job_events``) and the meter provider never
attaching the PrometheusMetricReader.
"""

from __future__ import annotations

import importlib.util

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service

# Narrowed: metrics and metrics_collector now ship (see the module docstring). These three
# still require the scaled fleet, so the hold on them is still load-bearing.
_HELD_MODULES = ("redis_backend", "worker", "worker_registry")


def test_scaled_modules_absent_on_this_branch():
    for name in _HELD_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is None, f"{full} must not ship on the single-node branch"


def test_the_promoted_job_metrics_do_ship():
    """The other half of the narrowing: what was promoted must actually be here.

    Without this, removing two names from the held list would silently assert nothing, and
    the modules could disappear again with no test noticing either way.
    """
    for name in ("metrics", "metrics_collector"):
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is not None, f"{full} was promoted and should ship"


def test_redis_request_degrades_to_in_process_without_scaled_modules(monkeypatch):
    """Constructing the facade with job_queue_type=redis must not raise.

    The scaled modules are absent, so the backend stays None and the in-process
    executor owns runs.
    """
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "job_queue_type", "redis")
    assert settings_service.settings.background_backend_is_scaled is True

    service = BackgroundExecutionService(settings_service)

    assert service._backend is None
    assert service._scaled is False
