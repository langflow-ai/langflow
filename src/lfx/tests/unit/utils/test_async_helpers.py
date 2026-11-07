"""Tests for ``run_until_complete`` contextvars propagation.

``run_until_complete`` has two branches: ``asyncio.run`` (no running loop) and a
worker-thread fallback (a loop is already running). The fallback must carry the
caller's contextvars into the new thread — lfx serve resolves request-scoped
variables and the no-env-fallback flag via ContextVars, and a bare
``ThreadPoolExecutor`` would otherwise reset them to their defaults.
"""

from __future__ import annotations

import asyncio
import contextvars

import pytest
from lfx.utils.async_helpers import run_until_complete, timeout_context

_probe_var: contextvars.ContextVar[str] = contextvars.ContextVar("probe_var", default="default")


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_seconds", [None, 60])
async def test_timeout_context_allows_work_before_deadline(timeout_seconds):
    async with timeout_context(timeout_seconds) as timeout:
        await asyncio.sleep(0)
        assert not timeout.expired()


@pytest.mark.asyncio
async def test_timeout_context_cancels_work_after_deadline():
    with pytest.raises(TimeoutError):
        async with timeout_context(0):
            await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_timeout_context_preserves_body_exception():
    error = ValueError("body failed")
    with pytest.raises(ValueError, match="body failed") as caught:
        async with timeout_context(None):
            raise error
    assert caught.value is error


@pytest.mark.asyncio
async def test_timeout_context_preserves_external_cancellation():
    entered = asyncio.Event()

    async def work():
        async with timeout_context(None):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_run_until_complete_propagates_contextvars_in_thread_fallback():
    """When a loop is already running, the worker-thread branch keeps the caller's ContextVars."""

    async def _read() -> str:
        return _probe_var.get()

    token = _probe_var.set("propagated")
    try:
        # pytest-asyncio runs this test inside a loop, so run_until_complete takes the
        # thread-hop branch. Before the fix this returned "default" (context reset).
        assert run_until_complete(_read()) == "propagated"
    finally:
        _probe_var.reset(token)


def test_run_until_complete_propagates_contextvars_in_run_branch():
    """With no running loop, the asyncio.run branch also sees the caller's ContextVars."""

    async def _read() -> str:
        return _probe_var.get()

    token = _probe_var.set("sync-path")
    try:
        assert run_until_complete(_read()) == "sync-path"
    finally:
        _probe_var.reset(token)
