"""Contextual classification tests for shell builtins.

Some builtins switch intent based on arguments rather than just the
leading binary. Today: ``set``. Without arguments or with a name lookup
it is read-only; with ``NAME=value`` it writes to the shell environment.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    "command",
    [
        "set",  # cmd.exe / sh: prints all env vars
        "set FOO",  # cmd.exe: prints value of FOO; sh: lists vars matching FOO
        "set PATH",  # prints PATH
        "SET",  # case-insensitive on Windows
    ],
)
def test_should_classify_set_without_assignment_as_read_only(command: str):
    assert classify_command(command) == CommandIntent.READ_ONLY


@pytest.mark.parametrize(
    "command",
    [
        "set FOO=bar",
        "set PATH=C:\\Windows",
        "set FOO=bar baz",
        "SET FOO=bar",
        "set foo=",  # empty assignment (clears var) is still a write
    ],
)
def test_should_classify_set_with_assignment_as_write(command: str):
    assert classify_command(command) == CommandIntent.WRITE


@pytest.mark.parametrize(
    "command",
    [
        "setx PATH C:\\foo",  # setx is always a write — separate binary
    ],
)
def test_setx_is_always_write(command: str):
    assert classify_command(command) == CommandIntent.WRITE
