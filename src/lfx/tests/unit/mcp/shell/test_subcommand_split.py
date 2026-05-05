"""Tests for the subcommand splitter."""

from __future__ import annotations

from lfx.mcp.shell.subcommand_split import split_subcommands


def test_should_return_single_command_when_no_operators():
    assert split_subcommands("ls -la") == ["ls -la"]


def test_should_split_on_semicolon():
    assert split_subcommands("ls; pwd") == ["ls", "pwd"]


def test_should_split_on_logical_and():
    assert split_subcommands("ls && pwd") == ["ls", "pwd"]


def test_should_split_on_logical_or():
    assert split_subcommands("ls || pwd") == ["ls", "pwd"]


def test_should_split_on_pipe():
    assert split_subcommands("cat foo | grep bar") == ["cat foo", "grep bar"]


def test_should_split_on_background_ampersand():
    assert split_subcommands("foo & bar") == ["foo", "bar"]


def test_should_split_on_newline():
    r"""POSIX sh treats an unquoted newline as a command terminator equivalent to ``;``.

    Regression guard for the read_only bypass where ``"ls\nrm x"`` was fed to the
    validator as a single subcommand and classification keyed only on ``ls``.
    """
    assert split_subcommands("ls\nrm somefile") == ["ls", "rm somefile"]


def test_should_split_on_carriage_return():
    r"""Treat ``\r`` as a separator so CRLF line endings don't survive a single subcommand.

    Windows-origin payloads carry CRLF; without this, ``"ls\r\nrm x"`` would
    persist as a single embedded literal.
    """
    assert split_subcommands("ls\r\nrm somefile") == ["ls", "rm somefile"]


def test_should_skip_newline_inside_double_quotes():
    """Quoted newlines are literal data, not separators.

    Symmetric to the existing ``;`` / ``|`` behavior inside quotes.
    """
    assert split_subcommands('echo "a\nb" && pwd') == ['echo "a\nb"', "pwd"]


def test_should_skip_operators_inside_double_quotes():
    assert split_subcommands('echo "a; b" && pwd') == ['echo "a; b"', "pwd"]


def test_should_skip_operators_inside_single_quotes():
    assert split_subcommands("echo 'a | b' ; pwd") == ["echo 'a | b'", "pwd"]


def test_should_handle_nested_alternation_of_quotes():
    assert split_subcommands("""echo 'a "b; c"' ; pwd""") == ["""echo 'a "b; c"'""", "pwd"]


def test_should_drop_empty_segments():
    assert split_subcommands(";;;") == []
    assert split_subcommands("ls ;; pwd") == ["ls", "pwd"]


def test_should_handle_empty_input():
    assert split_subcommands("") == []


def test_should_return_only_non_empty_segments():
    assert split_subcommands("  ; ls ;  ") == ["ls"]
