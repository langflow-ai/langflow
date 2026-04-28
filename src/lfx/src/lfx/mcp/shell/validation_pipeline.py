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
from lfx.mcp.shell.redirect_detection import has_write_redirect
from lfx.mcp.shell.shell_types import CommandIntent, RejectionReason, ValidationResult
from lfx.mcp.shell.subcommand_split import split_subcommands
from lfx.mcp.shell.substitution_detection import has_command_substitution
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
    # Substitution check runs on the raw command, *before* split.
    # ``echo $(rm -rf /)`` is one subcommand to the splitter but the
    # inner command bypasses every other stage's regex anchors.
    if has_command_substitution(command):
        return ValidationResult.reject(
            RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED,
            "Command rejected: shell command substitution ($(...) or `...`) is not allowed. "
            "Run the inner command separately and pass its result as a literal argument.",
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
    intent = _effective_intent(sub)
    mode_check = validate_mode(intent, config.mode)
    if not mode_check.is_ok:
        return mode_check
    return validate_paths(sub, working_directory=config.working_directory)


def _effective_intent(sub: str) -> CommandIntent:
    """Classify ``sub`` and escalate to WRITE if a write redirect is present.

    A read-only command followed by ``>`` / ``>>`` / ``2>`` actually
    writes to disk. Without this escalation, ``echo evil > file`` would
    pass read_only mode because ``echo`` itself is read-only.
    """
    intent = classify_command(sub)
    if intent is CommandIntent.READ_ONLY and has_write_redirect(sub):
        return CommandIntent.WRITE
    return intent
