"""Tests for command substitution detection.

``$(...)`` (POSIX + PowerShell) and `` `...` `` (POSIX backticks) wrap
arbitrary commands inside a string. Anything we statically validate
about the outer command tells us nothing about what runs inside the
substitution. The destructive payload could be anywhere — ``echo $(rm
-rf /)`` will literally execute ``rm -rf /``.

There is no safe static way to validate the inner command (it can
itself contain substitutions, env-var dereferences, etc.), so we
refuse the construct outright. Agents that need a command's output
must run it as a separate ``execute_command`` call.

Single-quoted regions are exempt — POSIX shells treat single-quoted
text as literal, so ``echo '$(rm -rf /)'`` does not expand.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.substitution_detection import has_command_substitution


@pytest.mark.parametrize(
    "command",
    [
        "echo $(rm -rf /)",
        "echo $(whoami)",
        "cat $(ls)",
        'printf "%s" "$(date)"',
        "Write-Host $(Get-Date)",
        "$(rm -rf /)",
        # Backticks (POSIX)
        "echo `whoami`",
        "echo `rm -rf /`",
        "result=`date`",
        # Nested
        "echo $(echo $(whoami))",
        # With pipes inside
        "echo $(ls | head)",
    ],
)
def test_should_detect_command_substitution(command: str):
    assert has_command_substitution(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "echo hello",
        "ls -la",
        "echo data > foo.txt",
        # Single-quoted: literal text, no expansion.
        "echo '$(rm -rf /)'",
        "echo '`whoami`'",
        # ``$VAR`` (no parens) is var expansion, not command substitution.
        "echo $HOME",
        "echo $PATH",
        "echo $env:USERPROFILE",  # PowerShell env var
        # Math expansion ``$((...))`` is arithmetic, not a command.
        # We currently err on the side of rejection (it could embed
        # commands via ``$(())`` corner cases) — see paranoid test below.
        # ``${VAR}`` brace expansion is not command substitution.
        "echo ${PATH}",
    ],
)
def test_should_not_detect_in_safe_commands(command: str):
    assert has_command_substitution(command) is False


def test_paranoid_should_detect_arithmetic_expansion_as_substitution():
    """Detect ``$((...))`` as substitution — defensive false-positive.

    Bash's ``$(())`` arithmetic expansion and command substitution share
    the ``$(`` opener. Detecting ``$((`` as substitution is a small
    false-positive that is safer than missing a real substitution.
    """
    assert has_command_substitution("echo $((1 + 1))") is True


def test_should_handle_empty_input():
    assert has_command_substitution("") is False


def test_should_ignore_substitution_inside_single_quotes():
    assert has_command_substitution("printf '%s' 'no $(real) substitution'") is False


def test_should_detect_substitution_inside_double_quotes():
    """Double-quoted strings DO expand in shells — must detect."""
    assert has_command_substitution('echo "user=$(whoami)"') is True
    assert has_command_substitution('echo "result `date`"') is True
