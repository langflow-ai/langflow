"""Validation pipeline orchestrator.

Sequences the four stages and applies them to every subcommand. First
failure short-circuits and is returned as the pipeline result.

Stages, in order:
  0. input length cap
  1. classify_command
  2. validate_not_destructive
  3. validate_mode
  4. validate_paths
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import RejectionReason, ValidationResult
from lfx.mcp.shell.subcommand_split import split_subcommands
from lfx.mcp.shell.validation_destructive import validate_not_destructive
from lfx.mcp.shell.validation_mode import validate_mode
from lfx.mcp.shell.validation_path import validate_paths

if TYPE_CHECKING:
    from lfx.mcp.shell.shell_config import ShellServerConfig


def run_validation_pipeline(command: str, config: ShellServerConfig) -> ValidationResult:
    if len(command) > config.max_command_length:
        return ValidationResult.reject(
            RejectionReason.INPUT_TOO_LARGE,
            f"Command rejected: input exceeds max_command_length ({config.max_command_length}).",
        )
    subcommands = split_subcommands(command)
    if not subcommands:
        return ValidationResult.reject(
            RejectionReason.UNKNOWN_CLASSIFICATION,
            "Command rejected: empty input.",
        )
    for sub in subcommands:
        outcome = _validate_subcommand(sub, config)
        if not outcome.is_ok:
            return outcome
    return ValidationResult.ok()


def _validate_subcommand(sub: str, config: ShellServerConfig) -> ValidationResult:
    destructive = validate_not_destructive(sub)
    if not destructive.is_ok:
        return destructive
    intent = classify_command(sub)
    mode_check = validate_mode(intent, config.mode)
    if not mode_check.is_ok:
        return mode_check
    return validate_paths(sub, working_directory=config.working_directory)
