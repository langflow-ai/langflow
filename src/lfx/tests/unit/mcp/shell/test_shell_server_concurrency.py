"""Tests for the concurrency guard rail.

Without a per-server cap, one client can issue N parallel
``execute_command`` calls and exhaust the host's PIDs/FDs/RAM, starving
every other tenant on the same Langflow backend. The cap is a fixed
``asyncio.Semaphore`` sized at ``config.max_concurrent``; callers that
sit in the queue longer than ``config.queue_timeout`` get a stable
``QUEUE_FULL`` rejection so the agent can retry instead of waiting
forever and exceeding the upstream proxy budget.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from lfx.mcp.shell import shell_server
from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig
from lfx.mcp.shell.shell_server import handle_execute_command
from lfx.mcp.shell.shell_types import ExecutionResult

if TYPE_CHECKING:
    from pathlib import Path


def _config(tmp_path: Path, **overrides: object) -> ShellServerConfig:
    from lfx.mcp.shell.shell_config import IsolationMode

    base = {
        "working_directory": str(tmp_path.resolve()),
        "mode": ShellMode.READ_WRITE,
        "max_timeout": 30,
        "max_output_bytes": 16 * 1024,
        "max_command_length": 4096,
        "max_concurrent": 4,
        "queue_timeout": 10,
        "isolation": IsolationMode.SHARED,
    }
    base.update(overrides)
    return ShellServerConfig(**base)


@pytest.fixture(autouse=True)
def _reset_semaphore() -> None:
    """Reset the module-level semaphore between tests.

    Each scenario starts with a fresh permit count tied to its own config.
    """
    shell_server._reset_concurrency_for_testing()
    yield
    shell_server._reset_concurrency_for_testing()


@pytest.mark.asyncio
async def test_should_serialize_commands_when_max_concurrent_is_one(
    tmp_path: Path,
) -> None:
    """With 1 permit, two concurrent calls must run back-to-back, not in parallel.

    The second waits for the first to release the permit.
    """
    in_flight = 0
    peak = 0

    async def fake_executor(*_args: object, **_kwargs: object) -> ExecutionResult:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.1)
        in_flight -= 1
        return ExecutionResult(stdout="", stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=fake_executor):
        await asyncio.gather(
            handle_execute_command(
                command="echo a",
                timeout=5,
                description="",
                config=_config(tmp_path, max_concurrent=1, queue_timeout=5),
            ),
            handle_execute_command(
                command="echo b",
                timeout=5,
                description="",
                config=_config(tmp_path, max_concurrent=1, queue_timeout=5),
            ),
        )

    assert peak == 1, f"semaphore=1 must serialize execution, observed peak={peak}"


@pytest.mark.asyncio
async def test_should_reject_with_queue_full_when_queue_timeout_exceeded(
    tmp_path: Path,
) -> None:
    """When permits are saturated, the call returns ``QUEUE_FULL`` past ``queue_timeout``.

    Rejection beats blocking the caller indefinitely.
    """
    release_first = asyncio.Event()

    async def slow_executor(*_args: object, **_kwargs: object) -> ExecutionResult:
        await release_first.wait()
        return ExecutionResult(stdout="", stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=slow_executor):
        # 1 permit; the first call holds it via slow_executor. The second
        # call's queue_timeout is short so it is rejected quickly.
        config = _config(tmp_path, max_concurrent=1, queue_timeout=1)
        first = asyncio.create_task(
            handle_execute_command(
                command="echo first",
                timeout=10,
                description="",
                config=config,
            )
        )
        await asyncio.sleep(0.05)  # let first acquire the permit
        second_payload = await handle_execute_command(
            command="echo second",
            timeout=10,
            description="",
            config=config,
        )
        release_first.set()
        await first

    assert second_payload["rejected"] is True
    assert second_payload["rejection_reason"] == "queue_full"
    assert second_payload["exit_code"] == -1


@pytest.mark.asyncio
async def test_should_release_permit_when_executor_raises(
    tmp_path: Path,
) -> None:
    """The semaphore must be released even if the executor blows up.

    Otherwise a single buggy command would permanently consume one of the few permits.
    """

    async def boom(*_args: object, **_kwargs: object) -> ExecutionResult:
        msg = "simulated executor failure"
        raise RuntimeError(msg)

    config = _config(tmp_path, max_concurrent=1, queue_timeout=1)
    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=boom):
        with pytest.raises(RuntimeError, match="simulated executor failure"):
            await handle_execute_command(
                command="echo a",
                timeout=5,
                description="",
                config=config,
            )

        # If the permit had leaked, this second call would either hang
        # or be QUEUE_FULL. With a clean release it runs immediately.
        async def ok(*_args: object, **_kwargs: object) -> ExecutionResult:
            return ExecutionResult(stdout="hi", stderr="", exit_code=0, timed_out=False)

        with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=ok):
            payload = await handle_execute_command(
                command="echo b",
                timeout=5,
                description="",
                config=config,
            )
    assert payload.get("rejected") is not True
    assert payload["exit_code"] == 0
