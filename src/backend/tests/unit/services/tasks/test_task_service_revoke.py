from __future__ import annotations

import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.task.service import TaskService


def _celery_enabled_service() -> TaskService:
    # Bypass __init__/get_backend so the sync/async tests run in envs
    # without the optional celery dependency installed.
    service = TaskService.__new__(TaskService)
    service.use_celery = True
    service.backend = None
    return service


def test_revoke_task_with_sync_backend_result():
    """TaskService must not await a synchronous backend result."""
    service = _celery_enabled_service()
    seen: list[str] = []

    class SyncBackend:
        def revoke_task(self, task_id: str) -> bool:
            seen.append(task_id)
            return True

    task_id = uuid4()
    service.backend = SyncBackend()
    assert asyncio.run(service.revoke_task(task_id)) is True
    assert seen == [str(task_id)]


def test_revoke_task_with_async_backend_result():
    """TaskService must still await an async backend result."""
    service = _celery_enabled_service()
    seen: list[str] = []

    class AsyncBackend:
        async def revoke_task(self, task_id: str) -> bool:
            seen.append(task_id)
            return True

    task_id = uuid4()
    service.backend = AsyncBackend()
    assert asyncio.run(service.revoke_task(task_id)) is True
    assert seen == [str(task_id)]


def test_revoke_task_celery_backend_broadcast():
    """Real Celery revoke broadcast must resolve to True, not raise TypeError."""
    pytest.importorskip("celery")
    from celery import Celery

    with (
        Celery("test-revoke", broker="memory://", set_as_current=False) as app,
        patch("langflow.worker.celery_app", app),
    ):
        from langflow.services.task.backends.celery import CeleryBackend

        service = _celery_enabled_service()
        service.backend = CeleryBackend()
        assert asyncio.run(service.revoke_task(uuid4())) is True
