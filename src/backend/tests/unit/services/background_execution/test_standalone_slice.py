"""The scaled backend ships with the slice, its selection is explicit, and the job metrics ship too.

Successor to the LE-1439 standalone guards: the scaled-backend modules
(``db_backend`` / ``worker``) now ship, because the durable job table is the
queue and there is no broker dependency left to hold back. ``metrics`` and
``metrics_collector`` ship for the same reason: they read the ``job`` and
``job_events`` tables only, so nothing in them needs a fleet to exist.

What must stay true: ``job_queue_type=redis`` (the v1 build-event queue) does
NOT drag the background backend into scaled mode, because selection is the
explicit ``background_backend`` setting. ``worker_registry`` is the one piece
still held: its gauges have no data until the worker roster lands.
"""

from __future__ import annotations

import importlib.util

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service

_SHIPPED_MODULES = ("db_backend", "worker", "metrics", "metrics_collector")
_HELD_MODULES = ("worker_registry",)


def test_scaled_modules_ship_with_the_slice():
    for name in _SHIPPED_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is not None, f"{full} must ship with the scaled backend"


def test_worker_roster_modules_stay_held():
    """The other half of the guard: what is still held must not appear unnoticed.

    Without this, a shipped list that grew by accident would assert nothing, and
    a half-ported roster could land with no test objecting either way.
    """
    for name in _HELD_MODULES:
        full = f"langflow.services.background_execution.{name}"
        assert importlib.util.find_spec(full) is None, f"{full} is not part of this slice yet"


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
