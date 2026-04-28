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
