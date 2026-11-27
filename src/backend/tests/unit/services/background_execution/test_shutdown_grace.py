"""A stopping API worker gives its background jobs ``background_shutdown_grace_s`` to finish."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.background_execution.factory import select_background_backend
from langflow.services.background_execution.service import BackgroundExecutionService


def _sleeper(seconds: float, finished: list[str], key: str):
    async def job():
        await asyncio.sleep(seconds)
        finished.append(key)

    return job


def _service(grace_s: float, *, backend=None) -> BackgroundExecutionService:
    settings = SimpleNamespace(
        background_backend_is_scaled=False,
        background_max_concurrency=1,
        background_shutdown_grace_s=grace_s,
        background_input_deadline_s=None,
        background_retention_days=0,
    )
    return BackgroundExecutionService(SimpleNamespace(settings=settings), backend=backend)


async def test_drain_waits_for_running_and_queued_jobs():
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    finished: list[str] = []
    try:
        await executor.submit("running", _sleeper(0.2, finished, "running"))
        await executor.submit("queued", _sleeper(0.2, finished, "queued"))

        await executor.drain(5)

        assert finished == ["running", "queued"]
    finally:
        await executor.stop()


async def test_drain_waits_for_a_job_submitted_while_it_waits():
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    finished: list[str] = []
    try:
        await executor.submit("first", _sleeper(0.2, finished, "first"))
        drain = asyncio.create_task(executor.drain(5))
        await asyncio.sleep(0.05)
        await executor.submit("late", _sleeper(0.1, finished, "late"))

        await drain

        assert finished == ["first", "late"]
    finally:
        await executor.stop()


async def test_drain_gives_up_at_its_timeout_and_stop_cancels_the_rest():
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    cancelled: list[str] = []

    async def outlasts_the_drain():
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append("job")
            raise

    await executor.submit("job", outlasts_the_drain)
    loop = asyncio.get_running_loop()
    started = loop.time()

    await executor.drain(0.3)

    assert 0.3 <= loop.time() - started < 2
    assert cancelled == []
    await executor.stop()
    assert cancelled == ["job"]


async def test_drain_without_jobs_returns_at_once():
    executor = InProcessExecutor()
    await executor.start()
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        await executor.drain(30)

        assert loop.time() - started < 0.5
    finally:
        await executor.stop()


async def test_drain_before_start_returns_at_once_and_keeps_queued_jobs():
    executor = InProcessExecutor()
    finished: list[str] = []
    await executor.submit("queued", _sleeper(0, finished, "queued"))
    loop = asyncio.get_running_loop()
    started = loop.time()

    await executor.drain(30)

    assert loop.time() - started < 0.5
    assert finished == []
    await executor.start()
    try:
        await asyncio.wait_for(executor.drain(5), timeout=2)
        assert finished == ["queued"]
    finally:
        await executor.stop()


async def test_service_drains_its_in_process_jobs_for_the_grace():
    service = _service(5)
    await service.start()
    finished: list[str] = []
    try:
        await service._executor.submit("job", _sleeper(0.2, finished, "job"))

        await service.drain()

        assert finished == ["job"]
    finally:
        await service.stop()


async def test_service_without_a_grace_leaves_jobs_for_stop_to_cancel():
    service = _service(0)
    await service.start()
    finished: list[str] = []
    try:
        await service._executor.submit("job", _sleeper(0.2, finished, "job"))
        loop = asyncio.get_running_loop()
        started = loop.time()

        await service.drain()

        assert loop.time() - started < 0.1
    finally:
        await service.stop()
    assert finished == []


async def test_scaled_backend_has_nothing_to_drain():
    settings = SimpleNamespace(
        background_backend_is_scaled=True,
        background_lease_ttl_s=45.0,
        background_poll_interval_s=0.5,
        background_claim_candidates=5,
    )
    backend = select_background_backend(settings, job_service=object(), owner="api:test")
    service = _service(30, backend=backend)
    loop = asyncio.get_running_loop()
    started = loop.time()

    await service.drain()

    assert loop.time() - started < 0.5
