"""Tests for Windows path validation.

Runs on every platform: ``validate_paths`` is a pure function that uses
``PureWindowsPath`` semantics when given Windows-shaped tokens, so the
test suite catches drive-letter and UNC issues even on macOS hosts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_path import validate_paths

if TYPE_CHECKING:
    from pathlib import Path


def test_should_reject_backslash_parent_traversal(tmp_path: Path):
    result = validate_paths("type ..\\..\\Windows\\System32\\config\\SAM", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_userprofile_env_reference(tmp_path: Path):
    result = validate_paths("type %USERPROFILE%\\Desktop\\notes.txt", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_appdata_env_reference(tmp_path: Path):
    result = validate_paths("type %APPDATA%\\foo", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_homedrive_homepath_combo(tmp_path: Path):
    result = validate_paths("type %HOMEDRIVE%%HOMEPATH%\\foo", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_powershell_env_userprofile(tmp_path: Path):
    result = validate_paths("Get-Content $env:USERPROFILE\\notes.txt", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_powershell_home_variable(tmp_path: Path):
    result = validate_paths("Get-Content $HOME\\notes.txt", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_unc_path(tmp_path: Path):
    result = validate_paths("type \\\\fileserver\\share\\secrets.txt", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_reject_drive_letter_path_when_token_is_outside_cwd(tmp_path: Path):
    # We can't make C:\Foo "inside" tmp_path on macOS, but the token uses a
    # Windows drive letter — we always treat it as outside on POSIX hosts.
    result = validate_paths("type C:\\Windows\\System32\\drivers\\etc\\hosts", working_directory=str(tmp_path))
    assert result.is_ok is False
    assert result.reason == RejectionReason.PATH_TRAVERSAL


def test_should_allow_relative_windows_path(tmp_path: Path):
    result = validate_paths("type .\\file.txt", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_allow_simple_filename_with_backslash_subdir(tmp_path: Path):
    result = validate_paths("type src\\lib\\foo.py", working_directory=str(tmp_path))
    assert result.is_ok is True


def test_should_allow_powershell_pipeline_with_safe_paths(tmp_path: Path):
    result = validate_paths("Get-ChildItem . | Select-Object Name", working_directory=str(tmp_path))
    assert result.is_ok is True
