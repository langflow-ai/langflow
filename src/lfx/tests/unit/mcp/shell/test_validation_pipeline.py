"""Tests for the validation pipeline orchestrator.

Pipeline order: input length -> split into subcommands -> each subcommand
runs through Stage 1 (classify) -> Stage 2 (destructive) -> Stage 3
(mode) -> Stage 4 (path). Early-return on the first failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.mcp.shell.shell_config import ShellMode, ShellServerConfig
from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_pipeline import run_validation_pipeline

if TYPE_CHECKING:
    from pathlib import Path


def _config(
    tmp_path: Path, *, mode: ShellMode = ShellMode.READ_WRITE, max_command_length: int = 4096
) -> ShellServerConfig:
    return ShellServerConfig(
        working_directory=str(tmp_path.resolve()),
        mode=mode,
        max_timeout=120,
        max_output_bytes=16 * 1024,
        max_command_length=max_command_length,
    )


def test_should_pass_for_simple_safe_command(tmp_path: Path):
    result = run_validation_pipeline("ls -la", _config(tmp_path))
    assert result.is_ok is True


def test_should_reject_input_longer_than_limit(tmp_path: Path):
    huge = "echo " + ("x" * 5000)
    result = run_validation_pipeline(huge, _config(tmp_path, max_command_length=128))
    assert result.is_ok is False
    assert result.reason == RejectionReason.INPUT_TOO_LARGE


def test_should_reject_destructive_pattern_before_mode_or_path(tmp_path: Path):
    result = run_validation_pipeline("rm -rf /", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


def test_should_reject_write_in_read_only_mode(tmp_path: Path):
    result = run_validation_pipeline(
        "touch newfile",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION


def test_should_reject_path_traversal(tmp_path: Path):
    result = run_validation_pipeline("cat ../etc/passwd", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_unknown_classification(tmp_path: Path):
    result = run_validation_pipeline("xyzzy_unknown_binary --help", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.UNKNOWN_CLASSIFICATION


def test_should_reject_when_any_subcommand_is_destructive(tmp_path: Path):
    """Composite commands: ``ls; rm -rf /`` must NOT slip past Stage 2."""
    result = run_validation_pipeline("ls; rm -rf /", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


def test_should_reject_when_pipe_chains_destructive(tmp_path: Path):
    result = run_validation_pipeline("cat foo | rm -rf /etc", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


def test_should_reject_when_logical_and_chains_destructive(tmp_path: Path):
    result = run_validation_pipeline("ls && rm -rf ~", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


def test_should_pass_safe_chained_commands(tmp_path: Path):
    result = run_validation_pipeline("ls && echo done", _config(tmp_path))
    assert result.is_ok is True


def test_should_pass_pipe_between_read_only_commands(tmp_path: Path):
    result = run_validation_pipeline("cat file.txt | grep foo", _config(tmp_path))
    assert result.is_ok is True


def test_should_reject_empty_command(tmp_path: Path):
    result = run_validation_pipeline("   ", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.UNKNOWN_CLASSIFICATION


# ---- Sec 3 — write-redirect bypasses read_only ----


def test_redirect_should_bypass_classification_and_be_treated_as_write_in_read_only(tmp_path: Path):
    """``echo data > file`` looks read-only but actually writes."""
    result = run_validation_pipeline(
        "echo data > evil.txt",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION


def test_append_redirect_should_be_blocked_in_read_only(tmp_path: Path):
    result = run_validation_pipeline(
        "cat foo >> log.txt",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION


def test_stderr_redirect_should_be_blocked_in_read_only(tmp_path: Path):
    result = run_validation_pipeline(
        "cat foo 2> err.log",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION


def test_powershell_redirect_should_be_blocked_in_read_only(tmp_path: Path):
    result = run_validation_pipeline(
        "Get-ChildItem > listing.txt",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.MODE_VIOLATION


def test_redirect_should_be_allowed_in_read_write(tmp_path: Path):
    """Redirects are normal usage in read_write — must keep working."""
    result = run_validation_pipeline(
        "echo data > out.txt",
        _config(tmp_path, mode=ShellMode.READ_WRITE),
    )
    assert result.is_ok is True


def test_redirect_in_quoted_string_should_not_trigger_escalation(tmp_path: Path):
    result = run_validation_pipeline(
        "echo 'data > file'",
        _config(tmp_path, mode=ShellMode.READ_ONLY),
    )
    assert result.is_ok is True


# ---- Sec 4 — command substitution must be refused ----


def test_should_reject_dollar_paren_substitution(tmp_path: Path):
    result = run_validation_pipeline("echo $(rm -rf /)", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED


def test_should_reject_backtick_substitution(tmp_path: Path):
    result = run_validation_pipeline("echo `whoami`", _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED


def test_should_reject_substitution_inside_double_quotes(tmp_path: Path):
    result = run_validation_pipeline('printf "%s" "$(date)"', _config(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED


def test_should_reject_substitution_in_read_write_too(tmp_path: Path):
    """Read_write doesn't soften the rule — substitution is always refused."""
    result = run_validation_pipeline(
        "echo $(whoami)",
        _config(tmp_path, mode=ShellMode.READ_WRITE),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED


def test_should_allow_substitution_inside_single_quotes(tmp_path: Path):
    """Single-quoted text is literal and never expanded."""
    result = run_validation_pipeline("echo '$(rm -rf /)'", _config(tmp_path))
    assert result.is_ok is True


def test_should_allow_dollar_var_without_paren(tmp_path: Path):
    """``$VAR`` is variable expansion, not command substitution."""
    result = run_validation_pipeline("echo $HOME", _config(tmp_path))
    # Note: $HOME triggers home-reference path validation -> path_traversal
    # but NOT substitution — confirm rejection_reason isn't substitution.
    assert result.reason != RejectionReason.SHELL_SUBSTITUTION_NOT_ALLOWED
