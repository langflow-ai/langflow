"""The whole scaled slice ships now, and its selection is still explicit.

Successor to the standalone guards that held the scaled-backend modules back.
``db_backend`` / ``worker`` ship because the durable job table is the queue and
there is no broker dependency left to hold. ``metrics`` / ``metrics_collector``
read the ``job`` and ``job_events`` tables only, so nothing in them needs a
fleet to exist, and they were promoted upstream ahead of this branch.
The worker roster was the last piece held, because its gauges had no data until
something populated it; the worker loop populates it now, so the held list is
empty. It lives with its model in ``database/models/worker_registry`` rather
than here, which is where this repo keeps table CRUD.

What must stay true: ``job_queue_type=redis`` (the v1 build-event queue) does
NOT drag the background backend into scaled mode, because selection is the
explicit ``background_backend`` setting.
"""

from __future__ import annotations

import importlib.util

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service

_SHIPPED_MODULES = ("db_backend", "worker", "metrics", "metrics_collector")


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

    from langflow.services.background_execution.in_process_backend import InProcessBackend

    assert isinstance(service._backend, InProcessBackend)
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
