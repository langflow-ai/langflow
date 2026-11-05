"""Bounded in-process executor: N concurrent workers draining an asyncio queue."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.executor import InProcessExecutor


@pytest.fixture
async def executor():
    ex = InProcessExecutor(max_concurrency=2)
    await ex.start()
    yield ex
    await ex.stop()


async def test_runs_submitted_job(executor):
    done = asyncio.Event()

    async def work():
        done.set()

    await executor.submit("job-1", work)
    await asyncio.wait_for(done.wait(), timeout=2)
    assert done.is_set()


async def test_respects_max_concurrency(executor):
    running = 0
    peak = 0
    release = asyncio.Event()

    async def work():
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await release.wait()
        running -= 1

    for i in range(5):
        await executor.submit(f"job-{i}", work)
    # Let workers pick up; with max_concurrency=2 at most 2 run at once.
    await asyncio.sleep(0.2)
    assert peak == 2
    release.set()


async def test_cancel_in_flight_job(executor):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def work():
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    await executor.submit("job-cancel", work)
    await asyncio.wait_for(started.wait(), timeout=2)
    assert await executor.cancel("job-cancel") is True
    await asyncio.wait_for(cancelled.wait(), timeout=2)


async def test_cancel_unknown_job_returns_false(executor):
    assert await executor.cancel("nope") is False


@pytest.mark.parametrize("worker_first", [True, False])
async def test_loop_shutdown_cancels_busy_worker(worker_first):
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    started = asyncio.Event()

    async def work():
        started.set()
        await asyncio.Event().wait()

    try:
        await executor.submit("shutdown-job", work)
        await asyncio.wait_for(started.wait(), timeout=2)
        job = executor._in_flight["shutdown-job"]
        worker = executor._workers[0]
        tasks = [worker, job] if worker_first else [job, worker]
        for task in tasks:
            task.cancel()

        # Runner.close cancels all pending tasks before waiting for their completion.
        # Use a bounded wait so a swallowed worker cancellation cannot hang pytest.
        done, pending = await asyncio.wait(tasks, timeout=1)
        assert not pending
        assert all(task.done() for task in done)
        assert not executor._in_flight
    finally:
        await executor.stop()


async def test_worker_survives_a_failing_job(executor):
    second_ran = asyncio.Event()

    async def boom():
        raise ValueError("boom")  # noqa: EM101

    async def ok():
        second_ran.set()

    await executor.submit("job-boom", boom)
    await executor.submit("job-ok", ok)
    await asyncio.wait_for(second_ran.wait(), timeout=2)
    assert second_ran.is_set()
