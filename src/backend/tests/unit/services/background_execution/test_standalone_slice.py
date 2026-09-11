"""The scaled backend ships with the slice and its selection is explicit.

Successor to the LE-1439 standalone guards: the scaled-backend modules
(``db_backend`` / ``worker``) now ship — the durable job table is the queue, so
there is no broker dependency to hold back. What must stay true instead:
``job_queue_type=redis`` (the v1 build-event queue) does NOT drag the
background backend into scaled mode — selection is the explicit
``background_backend`` setting.
"""

from __future__ import annotations

import importlib.util

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service

_SHIPPED_MODULES = ("db_backend", "worker")


def test_scaled_modules_ship_with_the_slice():
    for name in _SHIPPED_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is not None, f"{full} must ship with the scaled backend"


def test_redis_job_queue_does_not_select_the_scaled_backend(monkeypatch):
    """job_queue_type=redis is the v1 event queue, not background-backend selection.

    The facade must stay on the in-process executor unless
    ``background_backend=scaled`` is set explicitly.
    """
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "job_queue_type", "redis")
    assert settings_service.settings.background_backend_is_scaled is False

    service = BackgroundExecutionService(settings_service)

    assert service._backend is None
    assert service._scaled is False
