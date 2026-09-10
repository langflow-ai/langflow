from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.task.service import TaskService


def _celery_enabled_service() -> TaskService:
    return TaskService(SimpleNamespace(settings=SimpleNamespace(celery_enabled=True)))


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
        assert asyncio.run(_celery_enabled_service().revoke_task(uuid4())) is True
