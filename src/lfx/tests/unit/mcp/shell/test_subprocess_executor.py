"""Tests for the async subprocess executor.

These tests run real subprocesses (sh -c) so we exercise the cwd
handling, timeout-with-kill behaviour, and env sanitisation end-to-end
on the actual platform.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from lfx.mcp.shell.subprocess_executor import execute_subprocess

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_should_capture_stdout_and_exit_zero(tmp_path: Path):
    result = await execute_subprocess("echo hello", working_directory=str(tmp_path), timeout=5)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_should_capture_stderr_and_nonzero_exit(tmp_path: Path):
    result = await execute_subprocess(
        "echo oops 1>&2; exit 3",
        working_directory=str(tmp_path),
        timeout=5,
    )
    assert result.exit_code == 3
    assert "oops" in result.stderr
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_should_run_in_specified_working_directory(tmp_path: Path):
    result = await execute_subprocess("pwd", working_directory=str(tmp_path), timeout=5)
    assert result.exit_code == 0
    assert str(tmp_path.resolve()) in result.stdout


@pytest.mark.asyncio
async def test_should_kill_process_when_timeout_exceeded(tmp_path: Path):
    result = await execute_subprocess("sleep 30", working_directory=str(tmp_path), timeout=1)
    assert result.timed_out is True
    assert result.exit_code != 0


@pytest.mark.asyncio
async def test_timeout_should_complete_quickly_after_kill(tmp_path: Path):
    """Timeout must really kill — no hanging on subprocess cleanup."""
    start = asyncio.get_event_loop().time()
    await execute_subprocess("sleep 30", working_directory=str(tmp_path), timeout=1)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 5  # generous bound; should be ~1s


@pytest.mark.asyncio
async def test_should_strip_secrets_from_environment_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFLOW_API_KEY", "super-secret-do-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "another-secret")
    result = await execute_subprocess(
        "env",
        working_directory=str(tmp_path),
        timeout=5,
    )
    assert "super-secret-do-not-leak" not in result.stdout
    assert "another-secret" not in result.stdout


@pytest.mark.asyncio
async def test_should_preserve_path_for_resolution(tmp_path: Path):
    """``which`` requires PATH — confirm it is forwarded to the child."""
    result = await execute_subprocess(
        "which sh",
        working_directory=str(tmp_path),
        timeout=5,
    )
    assert result.exit_code == 0
    assert "/sh" in result.stdout
