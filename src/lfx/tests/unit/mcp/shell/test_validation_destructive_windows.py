"""Tests for Windows-flavoured destructive patterns.

These run on every platform — the validator only inspects strings, so
we can verify the regex catches Windows-style attacks even from macOS.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_destructive import validate_not_destructive


@pytest.mark.parametrize(
    "command",
    [
        "format C:",
        "format C: /Q",
        "format D: /FS:NTFS",
        "format E: /Y",
    ],
)
def test_should_reject_format_drive(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "del /F /S /Q C:\\",
        "del /F /S /Q C:\\*",
        "del /F /S /Q C:\\Windows",
        "del /S /Q C:\\Windows\\*",
        "erase /S /Q C:\\*",
    ],
)
def test_should_reject_recursive_del_on_root_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "rd /S /Q C:\\",
        "rd /S /Q C:\\Windows",
        "rmdir /S /Q C:\\",
    ],
)
def test_should_reject_recursive_rd_on_root_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "cipher /w:C:",
        "cipher /w:C:\\",
        r"cipher /w:C:\Users",
    ],
)
def test_should_reject_cipher_secure_delete(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "shutdown /s /t 0",
        "shutdown /r /f",
        "shutdown -s -t 0",  # POSIX-style flags also accepted by shutdown.exe
        "shutdown /p",  # immediate power off
    ],
)
def test_should_reject_windows_shutdown(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "vssadmin delete shadows /all",
        "vssadmin Delete Shadows /All /Quiet",
    ],
)
def test_should_reject_vssadmin_delete_shadows(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        r"reg delete HKLM\SYSTEM /f",
        r"reg delete HKEY_LOCAL_MACHINE\SOFTWARE /f",
        r"reg delete HKCU\Software /f",
        r"reg delete HKEY_CURRENT_USER\Software /f",
    ],
)
def test_should_reject_reg_delete_on_sensitive_hives(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "Remove-Item -Recurse -Force C:\\",
        "Remove-Item -Force -Recurse C:\\Windows",
        "Remove-Item -Recurse -Force $env:USERPROFILE",
        "Remove-Item -Recurse -Force $HOME",
    ],
)
def test_should_reject_powershell_remove_item_on_root_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "del file.txt",
        "del foo.bak",
        "del C:\\Users\\me\\project\\build\\old.log",
        "rd .\\build",
        "Remove-Item .\\build",
        "Remove-Item -Recurse -Force .\\build",
    ],
)
def test_should_allow_safe_or_scoped_windows_commands(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is True
