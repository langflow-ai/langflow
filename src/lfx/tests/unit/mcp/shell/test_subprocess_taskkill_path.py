r"""Tests that ``taskkill`` is invoked via an absolute path on Windows.

Resolving ``taskkill`` via ``%PATH%`` is an attack surface: the working
directory is shared and writable in the default configuration, so an
agent could plant a fake ``taskkill.exe`` there and hijack the kill
path. Anchoring the resolution to ``%SystemRoot%\System32\taskkill.exe``
blocks that bypass — only an attacker with write access to the Windows
system directory could substitute the real binary, at which point the
host is already compromised.
"""

from __future__ import annotations

import ntpath
from unittest.mock import AsyncMock

import pytest
from lfx.mcp.shell import subprocess_executor


@pytest.mark.asyncio
async def test_should_invoke_taskkill_via_systemroot_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)
    monkeypatch.setenv("SystemRoot", r"C:\Windows")

    captured: list[tuple] = []

    async def fake_exec(*args: object, **_kwargs: object) -> AsyncMock:
        captured.append(args)
        result = AsyncMock()
        result.wait = AsyncMock(return_value=0)
        return result

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    proc = AsyncMock()
    proc.pid = 1212
    proc.returncode = None

    await subprocess_executor._kill_tree_windows(proc)

    assert captured, "taskkill must have been invoked"
    invoked_path = captured[0][0]
    assert ntpath.isabs(invoked_path), (
        f"taskkill must be invoked via an absolute path, got {invoked_path!r}"
    )
    assert invoked_path.lower().endswith("taskkill.exe")
    # The path must include the SystemRoot directory so a malicious
    # ``taskkill`` planted on PATH cannot be used in its place.
    assert r"\Windows\System32" in invoked_path or "/Windows/System32" in invoked_path


@pytest.mark.asyncio
async def test_should_fall_back_to_default_systemroot_when_env_var_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r"""Fall back to the documented default ``C:\Windows`` when the env var is missing.

    The fallback must never silently re-introduce PATH-based resolution.
    """
    monkeypatch.setattr(subprocess_executor, "_IS_WINDOWS", True)
    monkeypatch.delenv("SystemRoot", raising=False)

    captured: list[tuple] = []

    async def fake_exec(*args: object, **_kwargs: object) -> AsyncMock:
        captured.append(args)
        result = AsyncMock()
        result.wait = AsyncMock(return_value=0)
        return result

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    proc = AsyncMock()
    proc.pid = 3434
    proc.returncode = None

    await subprocess_executor._kill_tree_windows(proc)

    assert captured, "taskkill must have been invoked"
    invoked_path = captured[0][0]
    assert ntpath.isabs(invoked_path)
    assert invoked_path.lower().endswith("taskkill.exe")
