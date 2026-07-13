"""LE-1439 guards: the kept background-execution slice is standalone.

The scaled-backend seam (``_build_scaled_backend`` / ``select_background_backend``)
ships upstream since release-1.11.0, but its modules (worker / redis_backend) do
not exist on this branch — so the functional contract is: requesting
``LANGFLOW_JOB_QUEUE_TYPE=redis`` must degrade to the in-process executor
instead of crashing on a missing import.
"""

from __future__ import annotations

import importlib.util

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service

_HELD_MODULES = ("redis_backend", "worker", "metrics", "metrics_collector", "worker_registry")


def test_scaled_and_observability_modules_absent_on_this_branch():
    for name in _HELD_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is None, f"{full} must not ship on the single-node branch"


def test_redis_request_degrades_to_in_process_without_scaled_modules(monkeypatch):
    """Constructing the facade with job_queue_type=redis must not raise: the scaled
    modules are absent, so the backend stays None and the in-process executor owns runs.
    """
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "job_queue_type", "redis")
    assert settings_service.settings.background_backend_is_scaled is True

    service = BackgroundExecutionService(settings_service)

    assert service._backend is None  # noqa: SLF001
    assert service._scaled is False  # noqa: SLF001
