"""Tests for Stage 2 — destructive pattern detection.

Adversarial matrix: variations with whitespace, sudo prefix, redirects.
The validator must reject regardless of formatting tricks.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.shell_types import RejectionReason
from lfx.mcp.shell.validation_destructive import validate_not_destructive


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "rm -rf /*",
        "rm  -rf  /",
        "rm -fr /",
        "rm -rf --no-preserve-root /",
        "sudo rm -rf /",
        "rm -rf ~",
        "rm -rf $HOME",
    ],
)
def test_should_reject_rm_rf_root_variants(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "mkfs /dev/sda",
        "mkfs.ext4 /dev/sda1",
        "mkfs.xfs /dev/sda",
    ],
)
def test_should_reject_mkfs(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "dd if=/dev/zero of=/dev/sda",
        "dd if=/dev/random of=/dev/sda",
        "dd if=/dev/urandom of=/dev/sdb bs=1M",
    ],
)
def test_should_reject_dd_to_device(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


def test_should_reject_fork_bomb():
    result = validate_not_destructive(":(){ :|:& };:")
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "chmod -R 777 /",
        "chmod -R 0777 /etc",
        "chown -R root:root /",
    ],
)
def test_should_reject_recursive_perm_change_on_root_paths(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "echo bad > /dev/sda",
        "cat data > /dev/nvme0n1",
    ],
)
def test_should_reject_redirect_to_block_device(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "shutdown -h now",
        "reboot",
        "halt",
        "init 0",
        "init 6",
    ],
)
def test_should_reject_power_management(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is False
    assert result.reason == RejectionReason.DESTRUCTIVE_PATTERN


@pytest.mark.parametrize(
    "command",
    [
        "ls",
        "rm file.txt",
        "rm -rf ./build",
        "cp -r src dst",
        "echo 'rm -rf /' > note.txt",  # in quotes only — not executed
    ],
)
def test_should_allow_safe_or_scoped_commands(command: str):
    result = validate_not_destructive(command)
    assert result.is_ok is True


def test_should_include_offending_pattern_in_message():
    result = validate_not_destructive("rm -rf /")
    assert result.is_ok is False
    assert "rm" in result.message.lower()
