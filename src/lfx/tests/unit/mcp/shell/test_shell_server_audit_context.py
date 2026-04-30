"""Tests for the audit-context plumbing in the MCP tool.

Without correlation IDs in the structured logs, an incident on a
multi-tenant Langflow backend ("which user ran ``rm -rf .``?") is
forensically dead — the only field we previously logged was
``description``, which is a free-form string controlled by the agent
and trivially forged. Plumbing the FastMCP ``Context`` through to the
handler gives us a stable ``request_id`` per call and the ``client_id``
of the MCP host whenever the transport supplies one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from lfx.mcp.shell import shell_server
from lfx.mcp.shell.audit_context import AuditContext
from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig
from lfx.mcp.shell.shell_server import handle_execute_command
from lfx.mcp.shell.shell_types import ExecutionResult

if TYPE_CHECKING:
    from pathlib import Path


def _config(tmp_path: Path) -> ShellServerConfig:
    from lfx.mcp.shell.shell_config import IsolationMode

    return ShellServerConfig(
        working_directory=str(tmp_path.resolve()),
        mode=ShellMode.READ_WRITE,
        max_timeout=30,
        max_output_bytes=16 * 1024,
        max_command_length=4096,
        max_concurrent=4,
        queue_timeout=10,
        isolation=IsolationMode.SHARED,
    )


@pytest.fixture(autouse=True)
def _reset_semaphore() -> None:
    shell_server._reset_concurrency_for_testing()
    yield
    shell_server._reset_concurrency_for_testing()


@pytest.mark.asyncio
async def test_should_include_request_id_in_accepted_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[tuple[str, dict]] = []

    def fake_info(event: str, **kwargs: object) -> None:
        captured.append((event, dict(kwargs)))

    monkeypatch.setattr("lfx.mcp.shell.shell_server.logger.info", fake_info)

    async def ok(*_args: object, **_kwargs: object) -> ExecutionResult:
        return ExecutionResult(stdout="", stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=ok):
        await handle_execute_command(
            command="echo a",
            timeout=5,
            description="user ran from playground",
            config=_config(tmp_path),
            audit_ctx=AuditContext(request_id="req-abc-123", client_id="claude-desktop"),
        )

    accepted = [(e, kw) for e, kw in captured if e == "shell_mcp.command_accepted"]
    assert accepted, f"expected 'shell_mcp.command_accepted' in {captured}"
    _, kwargs = accepted[0]
    assert kwargs.get("request_id") == "req-abc-123"
    assert kwargs.get("client_id") == "claude-desktop"


@pytest.mark.asyncio
async def test_should_include_request_id_in_rejected_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[tuple[str, dict]] = []

    def fake_info(event: str, **kwargs: object) -> None:
        captured.append((event, dict(kwargs)))

    monkeypatch.setattr("lfx.mcp.shell.shell_server.logger.info", fake_info)

    await handle_execute_command(
        command="rm -rf /",
        timeout=5,
        description="adversarial",
        config=_config(tmp_path),
        audit_ctx=AuditContext(request_id="req-evil-1", client_id=None),
    )

    rejected = [(e, kw) for e, kw in captured if e == "shell_mcp.command_rejected"]
    assert rejected, f"expected 'shell_mcp.command_rejected' in {captured}"
    _, kwargs = rejected[0]
    assert kwargs.get("request_id") == "req-evil-1"
    # client_id may be None — the field must still be present so log
    # filtering (e.g. "field exists") behaves consistently across calls.
    assert "client_id" in kwargs


@pytest.mark.asyncio
async def test_should_handle_missing_audit_context_without_breaking(
    tmp_path: Path,
) -> None:
    """Existing callers that omit ``audit_ctx`` must continue to work.

    Logs simply omit the IDs in that case.
    """

    async def ok(*_args: object, **_kwargs: object) -> ExecutionResult:
        return ExecutionResult(stdout="hi", stderr="", exit_code=0, timed_out=False)

    with patch("lfx.mcp.shell.shell_server.execute_subprocess", new=ok):
        payload = await handle_execute_command(
            command="echo a",
            timeout=5,
            description="",
            config=_config(tmp_path),
        )
    assert payload["exit_code"] == 0
    assert payload.get("rejected") is not True
