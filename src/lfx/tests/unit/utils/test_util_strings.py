"""Tests for lfx.utils.util_strings helpers."""

from lfx.utils.util_strings import escape_like_pattern


def test_escape_like_pattern_escapes_wildcards_and_escape_char():
    # % and _ are LIKE wildcards; backslash is the escape char and must be doubled first.
    assert escape_like_pattern("a%b_c") == r"a\%b\_c"
    assert escape_like_pattern("100%") == r"100\%"
    assert escape_like_pattern("a_b") == r"a\_b"
    # Backslash doubled before the wildcards are escaped (order matters).
    assert escape_like_pattern("a\\b") == "a\\\\b"
    assert escape_like_pattern("\\%") == "\\\\\\%"


def test_escape_like_pattern_leaves_plain_text_unchanged():
    assert escape_like_pattern("plain text 123") == "plain text 123"
    assert escape_like_pattern("") == ""
