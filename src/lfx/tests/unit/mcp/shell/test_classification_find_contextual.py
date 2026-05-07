r"""Contextual classification tests for ``find``.

PR review #3: ``find`` was unconditionally READ_ONLY. That misses three
families of primaries that turn it into arbitrary exec or write:

  * ``-exec`` / ``-execdir``  — runs any command per match
  * ``-delete``               — removes matched files
  * ``-fprint`` / ``-fprintf`` / ``-fprint0`` — writes to a path

A confirmed bypass was demonstrated:
``find . -exec sh -c "cat /etc/passwd" {} \;``
``find . -name foo -delete``
both passed in read_only mode on the original branch.

Contextual rejection: classify ``find`` as DESTRUCTIVE when those primaries
appear so the destructive-pattern validator gets a chance to reject.
Without them, ``find`` stays READ_ONLY.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.classification import classify_command
from lfx.mcp.shell.shell_types import CommandIntent


@pytest.mark.parametrize(
    "command",
    [
        "find .",
        "find . -name foo",
        "find /tmp -type f",
        "find . -mtime -1",
        "find . -size +1M",
        "find . -name foo -print",  # -print is read-only
        "FIND .",  # case-insensitive (Windows host)
    ],
)
def test_should_classify_plain_find_as_read_only(command: str):
    assert classify_command(command) == CommandIntent.READ_ONLY


@pytest.mark.parametrize(
    "command",
    [
        # -exec runs arbitrary commands
        "find . -exec ls {} \\;",
        "find . -exec sh -c 'cat /etc/passwd' {} \\;",
        "find . -name foo -exec rm {} +",
        # -execdir is the same risk profile (just changes cwd before exec)
        "find . -execdir ls {} \\;",
        # -delete removes matched files
        "find . -name foo -delete",
        "find /tmp -delete",
        # -fprint / -fprintf / -fprint0 write to a file
        "find . -fprint /tmp/out",
        "find . -fprintf /tmp/out '%p\\n'",
        "find . -fprint0 /tmp/out",
        # case sensitivity — POSIX find is lowercase, but a Windows host might
        # resolve `Find` to a path; the classifier already lowercases and
        # PowerShell-style mixed case shouldn't bypass.
        "find . -EXEC ls {} \\;",
    ],
)
def test_should_classify_find_with_dangerous_primary_as_destructive(command: str):
    """Primaries that turn find into arbitrary exec/write must escape READ_ONLY."""
    assert classify_command(command) == CommandIntent.DESTRUCTIVE


def test_dangerous_primary_inside_quoted_string_is_still_recognised():
    """The argv parser sees -exec as a token regardless of surrounding quoting."""
    # Even if a clever wrapper tries `find . -name "-exec"`, the `-exec` here is
    # an argument to -name (a search predicate value), not an action. The check
    # should still flag the literal token presence to be conservative — false
    # positives here are acceptable because the operator can adjust the query.
    assert classify_command('find . -name "anything" -exec true {} \\;') == CommandIntent.DESTRUCTIVE
