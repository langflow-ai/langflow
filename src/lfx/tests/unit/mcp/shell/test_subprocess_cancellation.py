"""Tests for cancellation- and exception-safe subprocess cleanup.

The executor must kill the spawned process tree on every abnormal exit
path -- not only on TimeoutError. Web clients disconnecting mid-call,
the host event loop shutting down, or any unexpected exception during
``communicate`` would otherwise leave orphan processes consuming CPU,
memory, file descriptors, and PIDs on the Langflow host.

These tests mock the subprocess primitives so they are deterministic on
POSIX and Windows alike (the platform-specific kill paths are covered
in ``test_subprocess_executor.py`` and ``test_subprocess_executor_windows.py``).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from lfx.mcp.shell.subprocess_executor import execute_subprocess

if TYPE_CHECKING:
    from pathlib import Path


def _make_hanging_proc() -> AsyncMock:
    """A fake Process whose communicate hangs until the task is cancelled or killed."""
    proc = AsyncMock()
    proc.returncode = None
    proc.pid = 99999

    async def _hang() -> tuple[bytes, bytes]:
        await asyncio.sleep(60)
        return b"", b""

    proc.communicate = _hang
    # ``wait`` resolves immediately so the cleanup path in ``finally``
    # does not stall the test for the full proc.wait timeout.
    proc.wait = AsyncMock(return_value=-9)
    return proc


@pytest.mark.asyncio
async def test_should_kill_process_tree_when_outer_task_is_cancelled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Cancelling the caller task must kill the spawned process before CancelledError propagates.

    Otherwise the subprocess outlives the request and becomes a zombie on the host.
    """
    proc = _make_hanging_proc()
    kill_called = asyncio.Event()

    async def fake_create(*_args: object, **_kwargs: object) -> AsyncMock:
        return proc

    async def fake_kill(target_proc: AsyncMock) -> None:
        kill_called.set()
        target_proc.returncode = -9

    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor.asyncio.create_subprocess_shell",
        fake_create,
    )
    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor._kill_process_tree",
        fake_kill,
    )

    task = asyncio.create_task(
        execute_subprocess(
            "noop",
            working_directory=str(tmp_path),
            timeout=300,
        )
    )
    # Yield once so the task enters wait_for(communicate) before we cancel.
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert kill_called.is_set(), (
        "_kill_process_tree must run when the outer task is cancelled"
    )


@pytest.mark.asyncio
async def test_should_kill_process_tree_when_communicate_raises_unexpected_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Any exception other than TimeoutError must still trigger the kill.

    We never trust the caller to clean up after us.
    """
    proc = _make_hanging_proc()
    kill_called = asyncio.Event()

    async def fake_create(*_args: object, **_kwargs: object) -> AsyncMock:
        return proc

    async def fake_kill(target_proc: AsyncMock) -> None:
        kill_called.set()
        target_proc.returncode = -9

    async def explode(*_args: object, **_kwargs: object) -> tuple[bytes, bytes]:
        msg = "simulated event-loop failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor.asyncio.create_subprocess_shell",
        fake_create,
    )
    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor._kill_process_tree",
        fake_kill,
    )
    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor.asyncio.wait_for",
        explode,
    )

    with pytest.raises(RuntimeError, match="simulated event-loop failure"):
        await execute_subprocess(
            "noop",
            working_directory=str(tmp_path),
            timeout=5,
        )

    assert kill_called.is_set(), (
        "_kill_process_tree must run when communicate raises an unexpected error"
    )


@pytest.mark.asyncio
async def test_should_not_double_kill_after_normal_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The cleanup path must not re-kill a process that finished normally.

    The guard rail must check returncode, not blindly fire kill on every exit.
    """
    proc = AsyncMock()
    proc.returncode = 0
    proc.pid = 12345

    async def fast_communicate() -> tuple[bytes, bytes]:
        return b"hello\n", b""

    proc.communicate = fast_communicate

    kill_calls = 0

    async def fake_kill(_target: AsyncMock) -> None:
        nonlocal kill_calls
        kill_calls += 1

    async def fake_create(*_args: object, **_kwargs: object) -> AsyncMock:
        return proc

    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor.asyncio.create_subprocess_shell",
        fake_create,
    )
    monkeypatch.setattr(
        "lfx.mcp.shell.subprocess_executor._kill_process_tree",
        fake_kill,
    )

    result = await execute_subprocess(
        "noop",
        working_directory=str(tmp_path),
        timeout=5,
    )

    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert kill_calls == 0, "no kill is expected when the process exits normally"
