"""TaskService.revoke_task must bridge the synchronous Celery backend (#14943).

``CeleryBackend.revoke_task`` publishes a revoke broadcast synchronously. The
service used to ``await`` its return value directly, so every Celery-mode
cancellation (workflow stop, KB ingestion cancel, memory-base delete) raised
``TypeError: object NoneType can't be used in 'await' expression``.

Celery is not a declared dependency, so the service-contract tests use a
synchronous stand-in backend and run everywhere; the real-Celery tests skip
unless ``celery`` is installed.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.task.service import TaskService


class _SyncRevokeBackend:
    """Stand-in with CeleryBackend's synchronous ``revoke_task`` contract."""

    name = "celery"

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def revoke_task(self, task_id: str) -> bool:
        self.calls.append((task_id, threading.get_ident()))
        if self.error is not None:
            raise self.error
        return True


def _celery_task_service(monkeypatch, backend) -> TaskService:
    monkeypatch.setattr("langflow.services.task.service.CeleryBackend", lambda: backend)
    return TaskService(SimpleNamespace(settings=SimpleNamespace(celery_enabled=True)))


async def test_celery_revoke_accepts_synchronous_backend(monkeypatch):
    backend = _SyncRevokeBackend()
    service = _celery_task_service(monkeypatch, backend)
    task_id = uuid4()

    assert await service.revoke_task(task_id) is True
    assert [sent_task_id for sent_task_id, _ in backend.calls] == [str(task_id)]


async def test_celery_revoke_publishes_off_the_event_loop(monkeypatch):
    backend = _SyncRevokeBackend()
    service = _celery_task_service(monkeypatch, backend)

    await service.revoke_task(uuid4())

    [(_, publish_thread)] = backend.calls
    assert publish_thread != threading.get_ident()


async def test_celery_revoke_propagates_broker_errors(monkeypatch):
    service = _celery_task_service(monkeypatch, _SyncRevokeBackend(error=ConnectionError("broker unavailable")))

    with pytest.raises(ConnectionError, match="broker unavailable"):
        await service.revoke_task(uuid4())


@pytest.fixture
def celery_app(monkeypatch):
    celery = pytest.importorskip("celery")
    # In-memory transport: exercises the real AsyncResult -> control -> kombu
    # publish path with no external broker and no worker.
    with celery.Celery("revoke-test", broker="memory://", set_as_current=False) as app:
        monkeypatch.setattr("langflow.worker.celery_app", app)
        yield app


def test_celery_backend_reports_published_revoke(celery_app, monkeypatch):
    """``AsyncResult.revoke`` returns ``None``; the backend must still report success."""
    from langflow.services.task.backends.celery import CeleryBackend

    sent = []
    original_revoke = celery_app.control.revoke

    def spy_revoke(task_id, **kwargs):
        sent.append((task_id, kwargs.get("terminate")))
        return original_revoke(task_id, **kwargs)

    monkeypatch.setattr(celery_app.control, "revoke", spy_revoke)
    task_id = str(uuid4())

    assert CeleryBackend().revoke_task(task_id) is True
    assert sent == [(task_id, True)]


async def test_task_service_revoke_with_real_celery(celery_app):
    """The reproduction from #14943, end to end through the real Celery backend."""
    service = TaskService(SimpleNamespace(settings=SimpleNamespace(celery_enabled=True)))

    assert service.backend.celery_app is celery_app
    assert await service.revoke_task(uuid4()) is True
