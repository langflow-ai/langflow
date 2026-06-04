"""Tests for ``run_until_complete`` contextvars propagation.

``run_until_complete`` has two branches: ``asyncio.run`` (no running loop) and a
worker-thread fallback (a loop is already running). The fallback must carry the
caller's contextvars into the new thread — lfx serve resolves request-scoped
variables and the no-env-fallback flag via ContextVars, and a bare
``ThreadPoolExecutor`` would otherwise reset them to their defaults.
"""

from __future__ import annotations

import contextvars

from lfx.utils.async_helpers import run_until_complete

_probe_var: contextvars.ContextVar[str] = contextvars.ContextVar("probe_var", default="default")


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
