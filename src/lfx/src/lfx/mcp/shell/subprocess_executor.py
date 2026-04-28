"""Async subprocess executor for the shell MCP server.

Runs a shell command inside a controlled working directory with a hard
timeout. On timeout the process tree is killed and the executor waits
for the child to terminate before returning, so callers never observe a
"timed out" result while the subprocess keeps running.

Environment is sanitised by default: only the variables in
``current_env_allowlist()`` are forwarded to the child, so secrets
(``LANGFLOW_API_KEY``, ``OPENAI_API_KEY``, etc.) do not leak into
commands the agent runs.

POSIX vs Windows
----------------
``asyncio.create_subprocess_shell`` picks the right interpreter for the
host: ``/bin/sh`` on POSIX, ``cmd.exe`` (or whatever ``COMSPEC`` points
at) on Windows. We diverge on two points:

* **Process grouping.** POSIX gets ``start_new_session=True`` so we own
  the process group via ``setsid``. Windows gets
  ``CREATE_NEW_PROCESS_GROUP`` for the same reason.
* **Tree kill.** POSIX uses ``killpg(SIGKILL)`` to take down the entire
  group. Windows shells out to ``taskkill /T /F /PID`` so any children
  spawned by ``cmd.exe`` (e.g. a PowerShell sub-shell, a slow
  ``mkdir`` chain) also terminate.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from typing import Any

from lfx.mcp.shell.shell_constants import current_env_allowlist
from lfx.mcp.shell.shell_types import ExecutionResult

_TIMEOUT_EXIT_CODE = -1
_IS_WINDOWS = os.name == "nt"


async def execute_subprocess(
    command: str,
    *,
    working_directory: str,
    timeout: int,
) -> ExecutionResult:
    """Run ``command`` via the platform shell and return an :class:`ExecutionResult`."""
    env = _sanitised_environment()
    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=working_directory,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **_process_group_kwargs(),
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        await _kill_process_tree(proc)
        stdout_bytes, stderr_bytes = await _drain_after_kill(proc)
        return ExecutionResult(
            stdout=stdout_bytes.decode(errors="replace"),
            stderr=(stderr_bytes.decode(errors="replace") + f"\n[killed after timeout of {timeout}s]"),
            exit_code=proc.returncode if proc.returncode is not None else _TIMEOUT_EXIT_CODE,
            timed_out=True,
        )
    return ExecutionResult(
        stdout=stdout_bytes.decode(errors="replace"),
        stderr=stderr_bytes.decode(errors="replace"),
        exit_code=proc.returncode if proc.returncode is not None else _TIMEOUT_EXIT_CODE,
        timed_out=False,
    )


def _sanitised_environment() -> dict[str, str]:
    parent = os.environ
    return {key: parent[key] for key in current_env_allowlist() if key in parent}


def _process_group_kwargs() -> dict[str, Any]:
    """Per-platform subprocess kwargs that give us a killable process group."""
    if _IS_WINDOWS:
        # ``CREATE_NEW_PROCESS_GROUP`` is required so taskkill /T can find
        # and terminate the whole tree we just spawned. The constant is
        # only defined on Windows builds of CPython, so we look it up
        # dynamically and fall back to its documented value (0x00000200)
        # so this module imports cleanly on POSIX hosts as well.
        import subprocess as _subprocess

        flag = getattr(_subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": flag}
    return {"start_new_session": True}


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if _IS_WINDOWS:
        await _kill_tree_windows(proc)
        return
    _kill_tree_posix(proc)


def _kill_tree_posix(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        # Already exited or out of our reach — fall back to killing the
        # leader directly. We still wait for it below.
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


async def _kill_tree_windows(proc: asyncio.subprocess.Process) -> None:
    """Use ``taskkill /T /F /PID`` to terminate the whole tree on Windows.

    ``taskkill`` is the only reliable way to take down children spawned
    by ``cmd.exe`` — calling ``proc.kill()`` only reaches the leader and
    can leave grandchildren orphaned.
    """
    try:
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/T",
            "/F",
            "/PID",
            str(proc.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(killer.wait(), timeout=5)
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        # taskkill missing or hung — fall back to terminating the leader.
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.kill()


async def _drain_after_kill(proc: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
    """Wait for the (now killed) process so its pipes close cleanly."""
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=5)
    except asyncio.TimeoutError:
        return (b"", b"")
