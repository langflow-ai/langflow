"""Tests for Windows-command classification.

These tests run on every platform — classification is a pure function
that just inspects the leading binary, so we can verify Windows commands
even when the test host is macOS/Linux.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    "command",
    [
        "dir",
        "dir C:\\Users",
        "type config.txt",
        "more file.txt",
        "where python",
        "whoami",
        "hostname",
        "tasklist",
        "tasklist /v",
        "ver",
        "vol",
        "tree",
        "fc a.txt b.txt",
        "comp a.txt b.txt",
        "findstr foo bar.txt",
        "systeminfo",
        "Get-ChildItem",
        "Get-Content",
        "Get-Process",
        "Select-String",
    ],
)
def test_should_classify_windows_read_only_commands(command: str):
    assert classify_command(command) == CommandIntent.READ_ONLY


@pytest.mark.parametrize(
    "command",
    [
        "copy a b",
        "xcopy src dst /E",
        "robocopy src dst",
        "move a b",
        "mklink link target",
        "md folder",
        "icacls foo /grant user:F",
        "attrib +R file",
        "Set-Content foo bar",
        "Add-Content foo bar",
        "New-Item -Path foo -ItemType File",
        "Out-File foo.txt",
    ],
)
def test_should_classify_windows_write_commands(command: str):
    assert classify_command(command) == CommandIntent.WRITE


@pytest.mark.parametrize(
    "command",
    [
        "del file.txt",
        "del /F /Q file.txt",
        "erase file.txt",
        "rd folder",
        "rmdir folder",
        "format C:",
        "cipher /w:C:",
        "Remove-Item foo",
        "Clear-Content foo",
    ],
)
def test_should_classify_windows_destructive_commands(command: str):
    assert classify_command(command) == CommandIntent.DESTRUCTIVE


@pytest.mark.parametrize(
    "command",
    [
        "ping example.com",
        "tracert example.com",
        "nslookup example.com",
        "ipconfig",
        "ipconfig /all",
        "netstat -an",
        "arp -a",
        "route print",
        "ftp host",
        "tftp host",
        "Invoke-WebRequest https://x",
        "Invoke-RestMethod https://x",
    ],
)
def test_should_classify_windows_network_commands(command: str):
    assert classify_command(command) == CommandIntent.NETWORK


@pytest.mark.parametrize(
    "command",
    [
        "taskkill /PID 1234",
        "taskkill /F /IM notepad.exe",
        "Stop-Process -Id 1234",
    ],
)
def test_should_classify_windows_process_management(command: str):
    assert classify_command(command) == CommandIntent.PROCESS_MANAGEMENT


@pytest.mark.parametrize(
    "command",
    [
        "choco install foo",
        "winget install foo",
        "scoop install foo",
        "Install-Module foo",
        "Install-Package foo",
    ],
)
def test_should_classify_windows_package_management(command: str):
    assert classify_command(command) == CommandIntent.PACKAGE_MANAGEMENT


@pytest.mark.parametrize(
    "command",
    [
        "net user",
        "net localgroup",
        "sc query",
        "runas /user:admin cmd",
        "reg query HKLM",
        "reg add HKLM",
        "reg delete HKLM",
        "wmic process",
        "bcdedit /enum",
        "shutdown /s /t 0",
        "shutdown /r",
        "gpupdate",
        "diskpart",
        "fsutil",
    ],
)
def test_should_classify_windows_system_admin(command: str):
    assert classify_command(command) == CommandIntent.SYSTEM_ADMIN


def test_should_classify_command_with_windows_path_prefix():
    assert classify_command(r"C:\Windows\System32\cmd.exe /c dir") == CommandIntent.UNKNOWN
    # The leading binary "cmd.exe" — strip extension by family rule
    assert classify_command(r"cmd.exe /c dir") == CommandIntent.UNKNOWN  # cmd not in table directly


def test_should_handle_powershell_cmdlet_case_insensitively():
    """PowerShell cmdlets are case-insensitive in real usage."""
    assert classify_command("get-childitem") == CommandIntent.READ_ONLY
    assert classify_command("REMOVE-ITEM foo") == CommandIntent.DESTRUCTIVE
