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
import locale
import os
import signal
from typing import Any

from lfx.mcp.shell.shell_constants import current_env_allowlist
from lfx.mcp.shell.shell_types import ExecutionResult

_TIMEOUT_EXIT_CODE = -1
_IS_WINDOWS = os.name == "nt"
# Bound for every wait that runs *after* a kill has been issued: pipe drain,
# proc.wait in the cleanup path, taskkill itself. Kept tight so the total
# response time stays well under common web-proxy budgets (Heroku 30s,
# nginx default 60s, Cloudflare 100s) — the kill has already fired, the
# child should be gone in milliseconds.
_POST_KILL_GRACE_SECONDS = 2


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
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            await _kill_process_tree(proc)
            stdout_bytes, stderr_bytes = await _drain_after_kill(proc)
            return ExecutionResult(
                stdout=_decode_output(stdout_bytes),
                stderr=_decode_output(stderr_bytes) + f"\n[killed after timeout of {timeout}s]",
                exit_code=proc.returncode if proc.returncode is not None else _TIMEOUT_EXIT_CODE,
                timed_out=True,
            )
        return ExecutionResult(
            stdout=_decode_output(stdout_bytes),
            stderr=_decode_output(stderr_bytes),
            exit_code=proc.returncode if proc.returncode is not None else _TIMEOUT_EXIT_CODE,
            timed_out=False,
        )
    finally:
        # Catches CancelledError (web client disconnect, server shutdown) and
        # any unexpected exception in communicate/wait_for so the spawned
        # process tree is never left running after this coroutine exits.
        # ``_kill_process_tree`` is idempotent — it no-ops once returncode
        # is set, so the timeout and happy paths above don't pay twice.
        if proc.returncode is None:
            await _kill_process_tree(proc)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(proc.wait(), timeout=_POST_KILL_GRACE_SECONDS)


def _select_output_encoding() -> str:
    """Encoding cmd.exe / sh emit on stdout.

    POSIX shells consistently emit UTF-8 on modern systems. Windows
    cmd.exe emits in the active OEM codepage (cp437/cp850/cp1252)
    unless the user runs ``chcp 65001`` first — decoding as UTF-8
    would corrupt accented filenames and box-drawing characters.
    """
    if _IS_WINDOWS:
        return locale.getpreferredencoding(do_setlocale=False) or "cp1252"
    return "utf-8"


def _decode_output(raw: bytes) -> str:
    return raw.decode(_select_output_encoding(), errors="replace")


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
    r"""Use ``taskkill /T /F /PID`` to terminate the whole tree on Windows.

    ``taskkill`` is the only reliable way to take down children spawned
    by ``cmd.exe`` — calling ``proc.kill()`` only reaches the leader and
    can leave grandchildren orphaned.

    The binary is resolved via ``%SystemRoot%\System32`` rather than
    via ``%PATH%``: the shell's working directory is shared and writable
    in the default config, so a hostile agent could otherwise plant a
    fake ``taskkill.exe`` there and hijack the kill path.
    """
    try:
        killer = await asyncio.create_subprocess_exec(
            _resolve_taskkill_path(),
            "/T",
            "/F",
            "/PID",
            str(proc.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(killer.wait(), timeout=_POST_KILL_GRACE_SECONDS)
    except (FileNotFoundError, asyncio.TimeoutError, OSError):
        # taskkill missing or hung — fall back to terminating the leader.
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.kill()


_DEFAULT_WINDOWS_SYSTEM_ROOT = r"C:\Windows"


def _resolve_taskkill_path() -> str:
    r"""Build the absolute path to ``taskkill.exe`` from ``%SystemRoot%``.

    Falls back to the documented default ``C:\Windows`` when the env
    var is missing — never resolves via ``%PATH%``.
    """
    # Why ``SystemRoot`` instead of ``SYSTEMROOT``: matches the env var name
    # Windows itself reports and the existing shell_constants allowlist.
    system_root = os.environ.get("SystemRoot") or _DEFAULT_WINDOWS_SYSTEM_ROOT  # noqa: SIM112
    return f"{system_root}\\System32\\taskkill.exe"


async def _drain_after_kill(proc: asyncio.subprocess.Process) -> tuple[bytes, bytes]:
    """Wait for the (now killed) process so its pipes close cleanly."""
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=_POST_KILL_GRACE_SECONDS)
    except asyncio.TimeoutError:
        return (b"", b"")
