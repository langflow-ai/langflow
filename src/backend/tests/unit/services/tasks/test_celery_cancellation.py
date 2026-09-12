"""Cancellation must support Celery's synchronous, fire-and-forget revoke API."""

import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.task.service import TaskService


@pytest.fixture
def celery_task_service(monkeypatch):
    celery = pytest.importorskip("celery")
    # Exercise the real AsyncResult/control/transport stack without an external
    # broker or a worker. A successful broadcast is not a worker acknowledgement.
    with celery.Celery("cancellation-test", broker="memory://", set_as_current=False) as app:
        monkeypatch.setattr("langflow.worker.celery_app", app)
        yield TaskService(SimpleNamespace(settings=SimpleNamespace(celery_enabled=True)))


@pytest.mark.no_blockbuster
async def test_celery_revoke_accepts_successful_broadcast(celery_task_service):
    assert await celery_task_service.revoke_task(uuid4()) is True


@pytest.mark.no_blockbuster
async def test_celery_revoke_runs_broker_io_off_event_loop(celery_task_service, monkeypatch):
    caller_thread = threading.get_ident()
    calls = []
    control = celery_task_service.backend.celery_app.control
    original_revoke = control.revoke

    def record_revoke(task_id, **kwargs):
        calls.append((threading.get_ident(), task_id, kwargs["terminate"]))
        return original_revoke(task_id, **kwargs)

    monkeypatch.setattr(control, "revoke", record_revoke)
    task_id = uuid4()
    assert await celery_task_service.revoke_task(task_id) is True
    assert len(calls) == 1
    worker_thread, sent_task_id, terminate = calls[0]
    assert worker_thread != caller_thread
    assert sent_task_id == str(task_id)
    assert terminate is True


async def test_celery_revoke_preserves_broker_failure(celery_task_service, monkeypatch):
    def fail_revoke(*_args, **_kwargs):
        message = "broker unavailable"
        raise ConnectionError(message)

    monkeypatch.setattr(celery_task_service.backend.celery_app.control, "revoke", fail_revoke)
    with pytest.raises(ConnectionError, match="broker unavailable"):
        await celery_task_service.revoke_task(uuid4())


async def test_celery_revoke_accepts_already_revoked_task(celery_task_service, monkeypatch):
    from celery.exceptions import TaskRevokedError

    def already_revoked(*_args, **_kwargs):
        raise TaskRevokedError

    monkeypatch.setattr(celery_task_service.backend.celery_app.control, "revoke", already_revoked)
    assert await celery_task_service.revoke_task(uuid4()) is True
