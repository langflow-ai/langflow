"""FastMCP server exposing ``execute_command`` for shell command execution.

This module is the thin handler layer: it wires together the validation
pipeline, subprocess executor, and output truncation. Business rules
live in their respective modules; the server just orchestrates and
formats the response.

The MCP tool is registered against a singleton :class:`FastMCP`. The
configuration is loaded once at import time so we never accidentally
honour an env var change made after the server boots.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

from mcp.server.fastmcp import FastMCP

from lfx.log.logger import logger
from lfx.mcp.shell.audit_context import AuditContext, from_fastmcp_context
from lfx.mcp.shell.output_truncation import truncate_output
from lfx.mcp.shell.shell_config import ShellServerConfig
from lfx.mcp.shell.shell_types import ExecutionResult, RejectionReason
from lfx.mcp.shell.subprocess_executor import execute_subprocess
from lfx.mcp.shell.validation_pipeline import run_validation_pipeline
from lfx.mcp.shell.working_directory_strategy import build_strategy

mcp = FastMCP(
    "langflow-shell",
    instructions=(
        "Langflow shell MCP server -- exposes a single tool, execute_command,\n"
        "for running shell commands inside a controlled working directory.\n\n"
        "Commands go through a multi-stage validation pipeline before execution:\n"
        "  1. Intent classification (read-only / write / destructive / network /\n"
        "     process / package / system-admin / unknown)\n"
        "  2. Destructive pattern detection (rm -rf /, mkfs, dd, fork bombs, ...)\n"
        "  3. Mode enforcement (read_only blocks anything beyond read-only)\n"
        "  4. Path validation (../, ~, $HOME, absolute paths outside cwd)\n\n"
        "Configuration via environment variables:\n"
        "  LANGFLOW_SHELL_WORKING_DIR     -- cwd for all commands (default: $PWD)\n"
        "  LANGFLOW_SHELL_MODE            -- read_write (default) or read_only\n"
        "  LANGFLOW_SHELL_MAX_TIMEOUT     -- upper bound per call (default 30s)\n"
        "  LANGFLOW_SHELL_MAX_OUTPUT_BYTES-- truncation threshold (default 16KB)\n"
        "  LANGFLOW_SHELL_MAX_COMMAND_LENGTH -- input cap (default 4KB)\n"
    ),
)

_config: ShellServerConfig | None = None
_semaphore: asyncio.Semaphore | None = None
_semaphore_capacity: int | None = None


def get_config() -> ShellServerConfig:
    global _config  # noqa: PLW0603 — singleton initialised on first access
    if _config is None:
        _config = ShellServerConfig.from_environment()
    return _config


def _get_semaphore(config: ShellServerConfig) -> asyncio.Semaphore:
    """Module-level concurrency permit pool.

    Sized once from the supplied config. If a caller passes a different
    ``max_concurrent`` (e.g. tests overriding the cap) the semaphore is
    rebuilt — production runs always pass the same singleton config so
    the rebuild is a no-op there.
    """
    global _semaphore, _semaphore_capacity  # noqa: PLW0603 — singleton lifecycle
    if _semaphore is None or _semaphore_capacity != config.max_concurrent:
        _semaphore = asyncio.Semaphore(config.max_concurrent)
        _semaphore_capacity = config.max_concurrent
    return _semaphore


def _reset_concurrency_for_testing() -> None:
    """Drop the cached semaphore so each test starts with fresh permits.

    Test-only helper — never call from production code.
    """
    global _semaphore, _semaphore_capacity  # noqa: PLW0603 — test-only reset
    _semaphore = None
    _semaphore_capacity = None


@mcp.tool()
async def execute_command(
    command: str,
    timeout: int = 30,
    description: str = "",
    ctx: object | None = None,
) -> dict[str, Any]:
    """Execute a shell command in the configured working directory.

    Args:
        command: Shell command to execute. Subject to a 4-stage
            validation pipeline; destructive patterns are rejected
            before execution.
        timeout: Max seconds before the process is killed. Clamped to
            the server-configured ``max_timeout``.
        description: Free-form text describing the purpose of the
            command. Recorded in the audit log; not used for execution.
        ctx: FastMCP request context, injected by the framework when
            available. Used to extract correlation IDs (request_id,
            client_id) for the structured audit log.

    Returns:
        Dict with keys ``stdout``, ``stderr``, ``exit_code``, ``timed_out``.
        On rejection, also includes ``rejected: true`` and a
        ``rejection_reason`` from a stable enum.
    """
    return await handle_execute_command(
        command=command,
        timeout=timeout,
        description=description,
        config=get_config(),
        audit_ctx=from_fastmcp_context(ctx),
    )


async def handle_execute_command(
    *,
    command: str,
    timeout: int,
    description: str,
    config: ShellServerConfig,
    audit_ctx: AuditContext | None = None,
) -> dict[str, Any]:
    """Stand-alone handler — no FastMCP coupling.

    Kept separate from the ``@mcp.tool()`` registration so unit tests
    can exercise the full pipeline without booting the server.
    """
    audit_fields = dict(audit_ctx.as_log_fields()) if audit_ctx is not None else {}
    try:
        clamped_timeout = config.clamp_timeout(timeout)
    except ValueError as exc:
        return _rejection(RejectionReason.INPUT_TOO_LARGE, str(exc))

    semaphore = _get_semaphore(config)
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=config.queue_timeout)
    except asyncio.TimeoutError:
        logger.info(
            "shell_mcp.command_queue_full",
            description=description,
            queue_timeout=config.queue_timeout,
            **audit_fields,
        )
        return _rejection(
            RejectionReason.QUEUE_FULL,
            f"Command rejected: server is at concurrency cap ({config.max_concurrent}); retry after a short backoff.",
        )

    try:
        # The strategy yields the working directory used for both path
        # validation and the subprocess; ephemeral mode allocates a fresh
        # tempdir per call so tenants never see each other's files.
        strategy = build_strategy(config.isolation, base_directory=config.working_directory)
        with strategy.acquire() as effective_workdir:
            effective_config = dataclasses.replace(config, working_directory=effective_workdir)
            validation = run_validation_pipeline(command, effective_config)
            if not validation.is_ok:
                assert validation.reason is not None  # noqa: S101 — invariant of ValidationResult.reject
                logger.info(
                    "shell_mcp.command_rejected",
                    reason=validation.reason.value,
                    description=description,
                    **audit_fields,
                )
                return _rejection(validation.reason, validation.message)

            logger.info(
                "shell_mcp.command_accepted",
                description=description,
                timeout=clamped_timeout,
                **audit_fields,
            )
            raw = await execute_subprocess(
                command,
                working_directory=effective_workdir,
                timeout=clamped_timeout,
            )
            truncated = _apply_truncation(raw, config.max_output_bytes)
            return truncated.to_dict()
    finally:
        semaphore.release()


def _rejection(reason: RejectionReason, message: str) -> dict[str, Any]:
    return ExecutionResult(
        stdout="",
        stderr=message,
        exit_code=-1,
        timed_out=False,
        rejected=True,
        rejection_reason=reason,
    ).to_dict()


def _apply_truncation(result: ExecutionResult, max_bytes: int) -> ExecutionResult:
    out_text, out_truncated = truncate_output(result.stdout, max_bytes=max_bytes)
    err_text, err_truncated = truncate_output(result.stderr, max_bytes=max_bytes)
    return ExecutionResult(
        stdout=out_text,
        stderr=err_text,
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        rejected=result.rejected,
        rejection_reason=result.rejection_reason,
        truncated=out_truncated or err_truncated,
    )
