"""End-to-end tests for the shell MCP server tool.

The MCP tool wires together the validation pipeline, subprocess
executor, and output truncation. Tests here check the response shape
for both success and rejection paths and verify that the executor is
not called when validation fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig
from lfx.mcp.shell.shell_server import handle_execute_command
from lfx.mcp.shell.shell_types import ExecutionResult

if TYPE_CHECKING:
    from pathlib import Path


def _config(tmp_path: Path, **overrides) -> ShellServerConfig:
    base = {
        "working_directory": str(tmp_path.resolve()),
        "mode": ShellMode.READ_WRITE,
        "max_timeout": 120,
        "max_output_bytes": 16 * 1024,
        "max_command_length": 4096,
    }
    base.update(overrides)
    return ShellServerConfig(**base)


@pytest.mark.asyncio
async def test_should_execute_safe_command_and_return_payload(tmp_path: Path):
    payload = await handle_execute_command(
        command="echo hi",
        timeout=5,
        description="smoke test",
        config=_config(tmp_path),
    )
    assert payload["exit_code"] == 0
    assert "hi" in payload["stdout"]
    assert payload["timed_out"] is False
    assert "rejected" not in payload


@pytest.mark.asyncio
async def test_should_reject_destructive_without_calling_executor(tmp_path: Path):
    with patch(
        "lfx.mcp.shell.shell_server.execute_subprocess",
        new=AsyncMock(),
    ) as executor:
        payload = await handle_execute_command(
            command="rm -rf /",
            timeout=5,
            description="adversarial",
            config=_config(tmp_path),
        )
    executor.assert_not_called()
    assert payload["rejected"] is True
    assert payload["rejection_reason"] == "destructive_pattern"
    assert payload["exit_code"] == -1
    assert payload["stdout"] == ""
    assert payload["stderr"]


@pytest.mark.asyncio
async def test_should_reject_in_read_only_mode(tmp_path: Path):
    payload = await handle_execute_command(
        command="touch x",
        timeout=5,
        description="",
        config=_config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert payload["rejected"] is True
    assert payload["rejection_reason"] == "mode_violation"


@pytest.mark.asyncio
async def test_should_clamp_timeout_to_server_max(tmp_path: Path):
    captured: dict[str, int] = {}

    async def _fake_executor(_command: str, *, working_directory: str, timeout: int) -> ExecutionResult:  # noqa: ARG001
        captured["timeout"] = timeout
        return ExecutionResult(stdout="", stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=_fake_executor):
        await handle_execute_command(
            command="echo ok",
            timeout=999,  # caller asks for 999s
            description="",
            config=_config(tmp_path, max_timeout=5),
        )
    assert captured["timeout"] == 5


@pytest.mark.asyncio
async def test_should_truncate_large_output(tmp_path: Path):
    big = "x" * 50_000

    async def _fake_executor(_command: str, *, working_directory: str, timeout: int) -> ExecutionResult:  # noqa: ARG001
        return ExecutionResult(stdout=big, stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=_fake_executor):
        payload = await handle_execute_command(
            command="echo ok",
            timeout=5,
            description="",
            config=_config(tmp_path, max_output_bytes=1024),
        )
    assert "truncated" in payload["stdout"]
    assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_should_treat_invalid_caller_timeout_as_rejection(tmp_path: Path):
    payload = await handle_execute_command(
        command="echo ok",
        timeout=0,
        description="",
        config=_config(tmp_path),
    )
    assert payload["rejected"] is True
    assert payload["exit_code"] == -1
