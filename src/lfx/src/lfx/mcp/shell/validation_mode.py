"""Stage 3 of the validation pipeline — mode enforcement.

Pure function over ``(intent, mode)``. In ``read_only`` mode, only
``READ_ONLY`` intents pass. ``UNKNOWN`` is fail-closed in V1: if Stage 1
could not classify the command, refuse it regardless of mode.
"""

from __future__ import annotations

from lfx.mcp.shell.shell_config import ShellMode
from lfx.mcp.shell.shell_types import CommandIntent, RejectionReason, ValidationResult


def validate_mode(intent: CommandIntent, mode: ShellMode) -> ValidationResult:
    if intent is CommandIntent.UNKNOWN:
        return ValidationResult.reject(
            RejectionReason.UNKNOWN_CLASSIFICATION,
            "Command rejected: unable to classify intent (fail-closed).",
        )
    if mode is ShellMode.READ_ONLY and intent is not CommandIntent.READ_ONLY:
        return ValidationResult.reject(
            RejectionReason.MODE_VIOLATION,
            f"Command rejected: server is in read_only mode (intent={intent.value}).",
        )
    return ValidationResult.ok()
