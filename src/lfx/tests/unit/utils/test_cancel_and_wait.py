"""Contract tests for ``cancel_and_wait``: one cancel, a bounded wait, no lost outcome.

The Starlette disconnect path that motivated it is covered end to end in
``tests/unit/workflow/test_router_stream_cancel.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from types import SimpleNamespace

import anyio
import pytest
from lfx.utils import async_helpers
from lfx.utils.async_helpers import cancel_and_wait

_GIVES_UP_AFTER = 5.0


class _Worker:
    """A task body that counts every cancel it sees and cleans up over several awaits."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancels = 0
        self.cleaned_up = False

    async def run(self) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancels += 1
            for _ in range(5):
                try:
                    await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    self.cancels += 1
            self.cleaned_up = True
            raise


async def test_a_cancelled_anyio_scope_does_not_re_cancel_the_task():
    worker = _Worker()
    task = asyncio.create_task(worker.run())
    await worker.started.wait()

    with anyio.CancelScope() as scope:
        scope.cancel()
        # Level-triggered: without the shield, every loop tick spent waiting in this
        # cancelled scope would be forwarded to ``task`` as another cancel.
        await cancel_and_wait(task, grace_seconds=5)

    assert worker.cancels == 1
    assert worker.cleaned_up
    assert task.cancelled()


async def test_a_cancel_aimed_at_the_caller_ends_the_wait_without_reaching_the_task():
    worker = _Worker()
    task = asyncio.create_task(worker.run())
    await worker.started.wait()

    caller = asyncio.create_task(cancel_and_wait(task, grace_seconds=5))
    await asyncio.sleep(0)
    caller.cancel()

    with pytest.raises(asyncio.CancelledError):
        await caller
    await asyncio.wait({task}, timeout=5)
    assert worker.cancels == 1
    assert worker.cleaned_up


async def test_re_raises_a_failure_other_than_the_cancellation():
    started = asyncio.Event()

    async def fail_on_cancel() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            msg = "cleanup failed"
            raise RuntimeError(msg) from None

    task = asyncio.create_task(fail_on_cancel())
    await started.wait()

    with pytest.raises(RuntimeError, match="cleanup failed"):
        await cancel_and_wait(task, grace_seconds=5)


async def test_a_task_that_outlives_the_wait_is_left_running_and_its_late_failure_logged(monkeypatch):
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        async_helpers,
        "logger",
        SimpleNamespace(warning=lambda msg, *_args, **kwargs: warnings.append((msg, kwargs))),
    )
    release = asyncio.Event()
    started = asyncio.Event()

    async def ignore_cancel_then_fail() -> None:
        started.set()
        # Gives up on its own so an unbounded wait fails the test instead of hanging it.
        deadline = time.monotonic() + _GIVES_UP_AFTER
        while not release.is_set() and time.monotonic() < deadline:
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.sleep(0.01)
        msg = "late failure"
        raise RuntimeError(msg)

    task = asyncio.create_task(ignore_cancel_then_fail())
    await started.wait()

    started_at = time.monotonic()
    await cancel_and_wait(task, grace_seconds=0.05)

    assert time.monotonic() - started_at < _GIVES_UP_AFTER / 2
    assert not task.done()
    assert len(warnings) == 1
    release.set()
    await asyncio.wait({task}, timeout=5)
    await asyncio.sleep(0)  # let the done callback run
    assert len(warnings) == 2
    assert isinstance(warnings[1][1]["exc_info"], RuntimeError)


async def test_a_cancelled_wait_still_logs_the_task_late_failure(monkeypatch):
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        async_helpers,
        "logger",
        SimpleNamespace(warning=lambda msg, *_args, **kwargs: warnings.append((msg, kwargs))),
    )
    release = asyncio.Event()
    started = asyncio.Event()

    async def fail_after_release() -> None:
        started.set()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.Event().wait()
        await asyncio.wait_for(release.wait(), timeout=_GIVES_UP_AFTER)
        msg = "late failure"
        raise RuntimeError(msg)

    task = asyncio.create_task(fail_after_release())
    await started.wait()
    caller = asyncio.create_task(cancel_and_wait(task, grace_seconds=_GIVES_UP_AFTER))
    await asyncio.sleep(0)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller

    release.set()
    await asyncio.wait({task}, timeout=_GIVES_UP_AFTER)
    await asyncio.sleep(0)  # let the done callback run
    assert [kwargs.get("exc_info") for _msg, kwargs in warnings if "exc_info" in kwargs]
    assert isinstance(warnings[-1][1]["exc_info"], RuntimeError)
