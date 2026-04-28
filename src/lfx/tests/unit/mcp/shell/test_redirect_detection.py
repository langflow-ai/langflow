"""Tests for shell write-redirect detection.

A subcommand can quietly write to disk via shell redirects (``>``,
``>>``, ``2>``, ``&>``, ``*>`` in PowerShell) even when the leading
binary is something read-only like ``echo`` or ``Get-Content``. We need
to recognise these so the pipeline can escalate the intent to WRITE
and refuse them in read_only mode.
"""

from __future__ import annotations

import pytest
from lfx.mcp.shell.redirect_detection import has_write_redirect


@pytest.mark.parametrize(
    "command",
    [
        "echo data > foo.txt",
        "echo data >> log.txt",
        "cat a > b",
        "printf x > x.txt",
        "grep foo bar.txt > matches.txt",
        "find . > listing.txt",
        "ls > out",
        "echo evil > .bashrc",
        "cat foo 2> err.log",
        "cat foo 2>> err.log",
        # PowerShell-style redirects
        "Get-ChildItem > listing.txt",
        "Get-Content cfg.json > out.json",
        "Get-Process *> all-streams.txt",
        # spacing variants
        "echo data>foo.txt",
        "echo data  >  foo.txt",
        "cat foo\t>\tbar.txt",
    ],
)
def test_should_detect_write_redirect(command: str):
    assert has_write_redirect(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "echo hello",
        "ls -la",
        "cat foo.txt",
        "grep foo bar.txt",
        # Pipes are not redirects — the pipeline already validates each
        # subcommand independently.
        "cat foo | grep bar",
        # ``<`` reads stdin, doesn't write — not our concern here.
        "wc -l < input.txt",
        # ``>`` inside a quoted string is just text, not a redirect.
        "echo 'data > file.txt'",
        'echo "redirect > x.txt" ',
        # Comparison operators in test/[ — not redirects (have spaces and
        # show up in test contexts; common false positive to avoid).
        "test 5 -gt 3",
        # ``=>`` is hash arrow — not in our scope but should not trip.
        "ruby -e 'puts {a: 1}'",
    ],
)
def test_should_not_detect_redirect_in_safe_commands(command: str):
    assert has_write_redirect(command) is False


def test_should_handle_empty_input():
    assert has_write_redirect("") is False


def test_should_ignore_redirect_inside_single_quotes():
    """Single-quoted ``>`` is a literal character, not a redirect."""
    assert has_write_redirect("echo 'rm -rf /' > /dev/null") is True  # outer > IS a redirect
    assert has_write_redirect("echo 'a > b'") is False
    assert has_write_redirect("printf '%s\\n' 'x>y'") is False


def test_should_ignore_redirect_inside_double_quotes():
    assert has_write_redirect('printf "x > y"') is False
    assert has_write_redirect('echo "result: 5 > 3"') is False
