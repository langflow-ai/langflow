"""Tests for the post-kill grace window.

After the timeout fires we must give the OS a brief moment to reap the
child and close pipes — but only briefly. Web clients sit behind
proxies (Heroku 30s, ALB 60s, Cloudflare 100s, nginx default 60s); a
generous post-kill window can push the total response time past the
proxy budget and leave the user with a 504 while we still hold the
subprocess.

The grace window is bounded by ``_POST_KILL_GRACE_SECONDS``. These
tests exercise it as a behaviour, not as a constant value, so a future
tweak that re-introduces a long wait would still fail the test.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from lfx.mcp.shell import subprocess_executor

if TYPE_CHECKING:
    from pathlib import Path


_GRACE_BUDGET_UPPER_BOUND = 3.5  # seconds — must be safely under 5s
_TIMEOUT_OBSERVATION_BUDGET = 1.5  # request timeout for the test scenario


@pytest.mark.asyncio
async def test_should_drain_within_grace_window_when_communicate_hangs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The drain step must give up within the grace window if pipes never close.

    Blocking longer would push the response past the upstream proxy budget.
    """
    proc = AsyncMock()
    proc.returncode = None
    proc.pid = 4242

    async def hang() -> tuple[bytes, bytes]:
        await asyncio.sleep(60)
        return b"", b""

    proc.communicate = hang
    proc.wait = AsyncMock(return_value=-9)

    async def fake_create(*_args: object, **_kwargs: object) -> AsyncMock:
        return proc

    async def fake_kill(target: AsyncMock) -> None:
        # ``returncode`` is intentionally NOT set to None → None so the
        # drain path below still hits the hanging communicate.
        target.returncode = None

    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor.asyncio.create_subprocess_shell",
        fake_create,
    )
    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor._kill_process_tree",
        fake_kill,
    )

    start = asyncio.get_event_loop().time()
    result = await subprocess_executor.execute_subprocess(
        "noop",
        working_directory=str(tmp_path),
        timeout=int(_TIMEOUT_OBSERVATION_BUDGET),
    )
    elapsed = asyncio.get_event_loop().time() - start

    assert result.timed_out is True
    assert elapsed < _GRACE_BUDGET_UPPER_BOUND, (
        f"post-kill drain budget exceeded: {elapsed:.2f}s "
        f"(must be < {_GRACE_BUDGET_UPPER_BOUND}s)"
    )


@pytest.mark.asyncio
async def test_should_give_up_taskkill_within_grace_window_when_taskkill_hangs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``taskkill`` itself hangs we must give up fast and fall back to ``proc.kill``.

    Rare but observed under heavy load — the alternative burns the proxy budget.
    """
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)

    proc = AsyncMock()
    proc.pid = 5555
    proc.returncode = None

    hung_taskkill = AsyncMock()

    async def hang() -> int:
        await asyncio.sleep(60)
        return 0

    hung_taskkill.wait = hang

    async def fake_exec(*_args: object, **_kwargs: object) -> AsyncMock:
        return hung_taskkill

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    start = asyncio.get_event_loop().time()
    await subprocess_executor._kill_tree_windows(proc)
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed < _GRACE_BUDGET_UPPER_BOUND, (
        f"taskkill grace budget exceeded: {elapsed:.2f}s"
    )
    proc.kill.assert_called_once()
