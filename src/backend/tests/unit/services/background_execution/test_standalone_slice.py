"""The scaled backend ships with the slice, its selection is explicit, and the metrics ship too.

Successor to the standalone guards that held the scaled-backend modules back.
``db_backend`` / ``worker`` now ship, because the durable job table is the queue
and there is no broker dependency left to hold. ``metrics`` /
``metrics_collector`` ship for a different reason: they read the ``job`` and
``job_events`` tables only, so nothing in them needs a fleet to exist, and they
were promoted upstream ahead of this branch.

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


def test_redis_job_queue_leaves_the_job_metrics_label_default(monkeypatch):
    """The metrics ``backend`` label names where jobs run, not what the settings asked for.

    Upstream this case was a degrade: ``job_queue_type=redis`` requested a scaled
    backend whose modules did not exist. Here the request never reaches backend
    selection at all, so the label must still read ``default`` for a reason the
    other test pins: redis no longer selects anything.
    """
    from langflow.services import deps
    from langflow.services.background_execution.metrics import current_backend

    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "job_queue_type", "redis")
    service = BackgroundExecutionService(settings_service)
    monkeypatch.setattr(deps, "get_background_execution_service", lambda: service)

    assert current_backend() == "default"


def test_wired_scaled_backend_labels_job_metrics_scaled(monkeypatch):
    """The label follows the wired backend, so it stays correct once one really ships."""
    from langflow.services import deps
    from langflow.services.background_execution.metrics import current_backend

    service = BackgroundExecutionService(get_settings_service(), backend=object())
    monkeypatch.setattr(deps, "get_background_execution_service", lambda: service)

    assert service.is_scaled is True
    assert current_backend() == "scaled"


def test_backend_label_defaults_when_the_service_is_unavailable(monkeypatch):
    """A tick must still label its series when the service lookup fails."""
    from langflow.services import deps
    from langflow.services.background_execution.metrics import current_backend

    def _unavailable():
        msg = "service manager torn down"
        raise RuntimeError(msg)

    monkeypatch.setattr(deps, "get_background_execution_service", _unavailable)

    assert current_backend() == "default"
