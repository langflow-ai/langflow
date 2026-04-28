"""Tests for Stage 4 — path validation.

Detects path traversal (``../``), home references (``~``, ``$HOME``),
and absolute paths that escape the configured working directory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_path import validate_paths

if TYPE_CHECKING:
    from pathlib import Path


def test_should_allow_command_without_paths(tmp_path: Path):
    result = validate_paths("echo hello", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_allow_relative_paths_inside_cwd(tmp_path: Path):
    result = validate_paths("cat ./file.txt", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_allow_simple_filename(tmp_path: Path):
    result = validate_paths("cat file.txt", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_allow_subdirectory_relative_paths(tmp_path: Path):
    result = validate_paths("cat src/lib/foo.py", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_reject_parent_directory_traversal(tmp_path: Path):
    result = validate_paths("cat ../etc/passwd", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL
    assert "../" in result.message


def test_should_reject_deep_parent_traversal(tmp_path: Path):
    result = validate_paths("cat ../../etc/passwd", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_tilde_reference(tmp_path: Path):
    result = validate_paths("cat ~/.ssh/id_rsa", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_home_env_var_reference(tmp_path: Path):
    result = validate_paths("cat $HOME/.aws/credentials", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_absolute_path_outside_working_directory(tmp_path: Path):
    other = tmp_path.parent / "other_dir"
    other.mkdir(exist_ok=True)
    result = validate_paths(
        f"cat {other}/secret.txt",
        working_directory=str(tmp_path),
    )
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_allow_absolute_path_inside_working_directory(tmp_path: Path):
    inside = tmp_path / "data"
    inside.mkdir()
    result = validate_paths(
        f"cat {inside}/file.txt",
        working_directory=str(tmp_path),
    )
    assert result.is_ok is True


def test_should_allow_dash_options_that_look_like_negative_numbers(tmp_path: Path):
    result = validate_paths("ls -la", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_ignore_short_options(tmp_path: Path):
    result = validate_paths("grep -n foo bar.txt", working_directory=str(tmp_path))
    assert result.is_ok is True
