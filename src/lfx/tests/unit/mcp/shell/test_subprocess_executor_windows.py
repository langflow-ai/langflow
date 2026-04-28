"""Cross-platform tests for the subprocess executor.

The real Windows code paths can only be exercised on a Windows host, so
on macOS/Linux we mock ``os.name`` and assert that the executor selects
the right kwargs and kill strategy. The POSIX paths remain covered by
``test_subprocess_executor.py`` with real subprocesses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from lfx.mcp.shell import subprocess_executor


def test_process_group_kwargs_should_use_setsid_on_posix(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", False)
    kwargs = subprocess_executor._process_group_kwargs()
    assert kwargs == {"start_new_session": True}


def test_process_group_kwargs_should_use_creation_flags_on_windows(monkeypatch: pytest.MonkeyPatch):
    """On Windows we need CREATE_NEW_PROCESS_GROUP so taskkill /T works."""
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)
    kwargs = subprocess_executor._process_group_kwargs()
    assert "start_new_session" not in kwargs
    assert "creationflags" in kwargs
    # The flag value comes from the subprocess module on real Windows;
    # on POSIX hosts the constant exists at runtime via this conditional
    # import. We just check the key is set with a positive int.
    assert isinstance(kwargs["creationflags"], int)
    assert kwargs["creationflags"] > 0


@pytest.mark.asyncio
async def test_kill_tree_should_dispatch_to_windows_implementation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)
    fake = AsyncMock()
    proc = AsyncMock()
    proc.returncode = None
    proc.pid = 4321
    monkeypatch.setattr(subprocess_executor, "_kill_tree_windows", fake)
    monkeypatch.setattr(subprocess_executor, "_kill_tree_posix", lambda *_a, **_k: None)
    await subprocess_executor._kill_process_tree(proc)
    fake.assert_awaited_once_with(proc)


def test_kill_tree_should_dispatch_to_posix_implementation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", False)
    called: list[bool] = []

    def _fake_posix(_proc):
        called.append(True)

    monkeypatch.setattr(subprocess_executor, "_kill_tree_posix", _fake_posix)
    proc = AsyncMock()
    proc.returncode = None
    proc.pid = 1234

    import asyncio

    asyncio.run(subprocess_executor._kill_process_tree(proc))
    assert called == [True]


@pytest.mark.asyncio
async def test_kill_tree_should_skip_when_process_already_finished(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)
    win_kill = AsyncMock()
    monkeypatch.setattr(subprocess_executor, "_kill_tree_windows", win_kill)
    proc = AsyncMock()
    proc.returncode = 0  # already finished
    await subprocess_executor._kill_process_tree(proc)
    win_kill.assert_not_called()


@pytest.mark.asyncio
async def test_kill_tree_windows_should_invoke_taskkill(monkeypatch: pytest.MonkeyPatch):
    captured_args: list[tuple] = []

    async def _fake_create_subprocess_exec(*args, **_kwargs):
        captured_args.append(args)
        result = AsyncMock()
        result.wait = AsyncMock(return_value=0)
        return result

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)
    proc = AsyncMock()
    proc.pid = 9999
    await subprocess_executor._kill_tree_windows(proc)
    assert captured_args, "taskkill should have been invoked"
    assert captured_args[0][0] == "taskkill"
    assert "/T" in captured_args[0]
    assert "/F" in captured_args[0]
    assert "/PID" in captured_args[0]
    assert "9999" in captured_args[0]


@pytest.mark.asyncio
async def test_kill_tree_windows_should_fallback_when_taskkill_missing():
    proc = AsyncMock()
    proc.pid = 7777

    error_message = "taskkill not found"

    async def _raise_filenotfound(*_args, **_kwargs):
        raise FileNotFoundError(error_message)

    with patch("asyncio.create_subprocess_exec", new=_raise_filenotfound):
        await subprocess_executor._kill_tree_windows(proc)
    proc.kill.assert_called_once()


def test_sanitised_environment_should_only_pass_allowlisted(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", "leak-this-please")
    monkeypatch.setenv("OPENAI_API_KEY", "and-this-too")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = subprocess_executor._sanitised_environment()
    assert "LANGFLOW_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    # PATH is in both POSIX and Windows allowlists, so it must pass.
    assert env.get("PATH") == "/usr/bin"
