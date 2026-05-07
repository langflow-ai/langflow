"""Tests for Stage 1 — command intent classification."""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("ls", CommandIntent.READ_ONLY),
        ("ls -la /tmp", CommandIntent.READ_ONLY),
        ("cat file.txt", CommandIntent.READ_ONLY),
        ("grep foo bar.txt", CommandIntent.READ_ONLY),
        ("head -n 5 a.txt", CommandIntent.READ_ONLY),
        ("tail -f a.log", CommandIntent.READ_ONLY),
        ("find . -name '*.py'", CommandIntent.READ_ONLY),
        ("pwd", CommandIntent.READ_ONLY),
        ("echo hello", CommandIntent.READ_ONLY),
        ("which python", CommandIntent.READ_ONLY),
        ("stat foo", CommandIntent.READ_ONLY),
        ("file foo", CommandIntent.READ_ONLY),
        ("wc -l x", CommandIntent.READ_ONLY),
        ("diff a b", CommandIntent.READ_ONLY),
        ("env", CommandIntent.READ_ONLY),
        ("printenv", CommandIntent.READ_ONLY),
    ],
)
def test_should_classify_read_only_commands(command: str, expected: CommandIntent):
    assert classify_command(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("touch newfile", CommandIntent.WRITE),
        ("mkdir folder", CommandIntent.WRITE),
        ("cp a b", CommandIntent.WRITE),
        ("mv a b", CommandIntent.WRITE),
        ("ln -s a b", CommandIntent.WRITE),
        ("chmod +x foo", CommandIntent.WRITE),
        ("chown user file", CommandIntent.WRITE),
        ("tar -czf out.tgz dir", CommandIntent.WRITE),
        ("zip -r out.zip dir", CommandIntent.WRITE),
        ("git commit -m msg", CommandIntent.WRITE),
        ("git add .", CommandIntent.WRITE),
    ],
)
def test_should_classify_write_commands(command: str, expected: CommandIntent):
    assert classify_command(command) == expected


# ``sed`` (and the wider scripting-engine family — awk/perl/tcl/lua/etc.)
# was historically WRITE here. PR review #4 reclassified them as UNKNOWN
# (fail-closed) because their script-body argv slot can hide arbitrary
# shell-exec primitives. See test_classification_scripting_engines_fail_closed.


@pytest.mark.parametrize(
    "command",
    [
        "rm file",
        "rm -rf folder",
        "rmdir folder",
        "shred file",
        "mkfs.ext4 /dev/sdb",
        "dd if=/dev/zero of=/dev/sda",
        "fdisk /dev/sda",
        "parted /dev/sda",
    ],
)
def test_should_classify_destructive_commands(command: str):
    assert classify_command(command) == CommandIntent.DESTRUCTIVE


@pytest.mark.parametrize(
    "command",
    [
        "curl https://example.com",
        "wget https://example.com",
        "ssh host",
        "scp a host:b",
        "nc -l 8080",
        "ping host",
        "telnet host",
    ],
)
def test_should_classify_network_commands(command: str):
    assert classify_command(command) == CommandIntent.NETWORK


@pytest.mark.parametrize(
    "command",
    [
        "kill 1234",
        "killall python",
        "pkill -f xyz",
        "nohup script.sh",
    ],
)
def test_should_classify_process_management_commands(command: str):
    assert classify_command(command) == CommandIntent.PROCESS_MANAGEMENT


@pytest.mark.parametrize(
    "command",
    [
        "apt install foo",
        "apt-get update",
        "yum install foo",
        "dnf install foo",
        "pip install foo",
        "pip3 install foo",
        "npm install foo",
        "yarn add foo",
        "brew install foo",
    ],
)
def test_should_classify_package_management_commands(command: str):
    assert classify_command(command) == CommandIntent.PACKAGE_MANAGEMENT


@pytest.mark.parametrize(
    "command",
    [
        "sudo ls",
        "su -",
        "systemctl restart nginx",
        "service nginx restart",
        "useradd bob",
        "userdel bob",
        "passwd bob",
        "iptables -L",
        "mount /dev/sda1 /mnt",
        "umount /mnt",
    ],
)
def test_should_classify_system_admin_commands(command: str):
    assert classify_command(command) == CommandIntent.SYSTEM_ADMIN


@pytest.mark.parametrize(
    "command",
    [
        "weird_unknown_binary --foo",
        "xyzzy",
        "",
    ],
)
def test_should_classify_unknown_commands(command: str):
    assert classify_command(command) == CommandIntent.UNKNOWN


def test_should_strip_leading_whitespace():
    assert classify_command("   ls -la") == CommandIntent.READ_ONLY


def test_should_handle_command_with_path_prefix():
    assert classify_command("/bin/ls") == CommandIntent.READ_ONLY
    assert classify_command("/usr/bin/rm -rf foo") == CommandIntent.DESTRUCTIVE
