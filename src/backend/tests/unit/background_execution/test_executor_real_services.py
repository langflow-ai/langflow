"""Verify the in-process executor's worker resilience.

These tests drive the REAL ``InProcessExecutor`` (no mocks of our logic) and
assert the worker pool survives the two ways a job can end abnormally:

* a job cancelled via ``cancel(key)`` must NOT take its worker down — the pool
  must keep accepting and completing later jobs (this is the path that broke on
  Python 3.10 where ``Task.cancelling()`` does not exist);
* a job that raises a non-``CancelledError`` exception must be caught and not
  kill the worker either.

Both are run with ``max_concurrency=1`` so a single dead worker is immediately
observable: if the only worker dies, the next submitted job hangs QUEUED and the
``asyncio.wait_for`` guard fails the test rather than hanging the suite.
"""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.executor import InProcessExecutor

pytestmark = pytest.mark.real_services


async def test_pool_survives_repeated_job_cancellation(monkeypatch):
    """Cancelling N jobs in a row must not kill the (single) worker.

    With one worker, each ``cancel(key)`` cancels the in-flight task. The worker
    must absorb that cancel, keep looping, and remain able to run a fresh job.

    The project supports Python 3.10, where ``asyncio.Task.cancelling()`` does
    NOT exist. The old worker used ``cancelling()`` to tell a job-cancel apart
    from a worker-cancel; on 3.10 that raised ``AttributeError`` inside the
    cancel handler and permanently killed the worker, so the final "fresh job
    completes" assertion would hang. We pin the 3.10 condition by wrapping the
    worker's ``current_task()`` in a proxy that has no ``cancelling`` so the test
    catches the bug on every interpreter (>=3.11 included), not just on a real
    3.10.
    """
    # Simulate Python 3.10: ``asyncio.current_task()`` returns a Task without a
    # ``cancelling`` method. We can't delete the attribute off the immutable C
    # ``_asyncio.Task`` type, so we wrap the real task in a proxy that exposes
    # everything EXCEPT ``cancelling`` — touching ``.cancelling`` raises
    # ``AttributeError`` exactly as it does on a real 3.10 interpreter. Patched
    # in the executor's namespace so only the worker sees the 3.10-shaped task.
    import langflow.services.background_execution.executor as executor_mod

    real_current_task = asyncio.current_task

    class _Py310TaskProxy:
        def __init__(self, task):
            object.__setattr__(self, "_task", task)

        def __getattr__(self, name):
            if name == "cancelling":
                msg = "'_asyncio.Task' object has no attribute 'cancelling'"
                raise AttributeError(msg)
            return getattr(self._task, name)

    def _fake_current_task():
        task = real_current_task()
        return _Py310TaskProxy(task) if task is not None else None

    monkeypatch.setattr(executor_mod.asyncio, "current_task", _fake_current_task)

    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    try:
        for i in range(5):
            started = asyncio.Event()
            key = f"job-{i}"

            async def _blocker(ev=started) -> None:
                ev.set()
                await asyncio.sleep(3600)  # block until cancelled

            await executor.submit(key, _blocker)
            await asyncio.wait_for(started.wait(), timeout=2.0)
            assert await executor.cancel(key) is True

        # The pool must still serve work after 5 cancellations.
        done = asyncio.Event()

        async def _quick() -> None:
            done.set()

        await executor.submit("fresh", _quick)
        # If the worker died, this hangs and wait_for fails the test.
        await asyncio.wait_for(done.wait(), timeout=2.0)
    finally:
        await executor.stop()


async def test_stop_awaits_in_flight_tasks():
    """``stop()`` leaves every in-flight task ``done()`` when it returns.

    A real job cancelled mid-flight reconciles its terminal status inside a
    shielded ``finally`` (a DB write). ``stop()`` cancels the in-flight tasks and
    then ``gather``s them so that work finishes before teardown, rather than
    racing a closing DB engine and leaving a "Task was destroyed but it is
    pending" warning. We capture the in-flight task handle and assert it (and its
    multi-turn shielded finalizer) is done the instant ``stop()`` returns — the
    awaited-teardown contract the gather guarantees.
    """
    running = asyncio.Event()
    finalized = asyncio.Event()

    async def _job() -> None:
        try:
            running.set()
            await asyncio.sleep(3600)  # block until cancelled
        finally:
            # The runner's terminal reconcile is a shielded await (a DB write)
            # that spans several event-loop turns. Model it so the task only
            # finishes after a real awaited finalizer, not the instant the
            # cancel is delivered.
            for _ in range(10):
                await asyncio.shield(asyncio.sleep(0.02))
            finalized.set()

    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    await executor.submit("job", _job)
    await asyncio.wait_for(running.wait(), timeout=2.0)

    # Capture the in-flight task before stop() clears the registry.
    in_flight = executor._in_flight["job"]

    await executor.stop()

    # If stop() awaited the in-flight task, it (and its shielded finalizer) are
    # done the moment stop() returns. A non-awaiting stop() leaves it pending.
    assert in_flight.done(), "stop() returned without awaiting the in-flight task"
    assert finalized.is_set(), "shielded finalizer did not complete before stop() returned"


async def test_pool_survives_job_exception():
    """A job raising a non-CancelledError must not kill the worker."""
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    try:

        async def _boom() -> None:
            msg = "intentional job failure"
            raise RuntimeError(msg)

        await executor.submit("boom", _boom)
        # Give the worker a beat to pick up and fail the bad job.
        await asyncio.sleep(0.1)

        done = asyncio.Event()

        async def _quick() -> None:
            done.set()

        await executor.submit("after-boom", _quick)
        await asyncio.wait_for(done.wait(), timeout=2.0)
    finally:
        await executor.stop()
