"""Tests for output truncation."""

from __future__ import annotations

from lfx.mcp.shell.output_truncation import truncate_output


def test_should_return_input_unchanged_when_under_limit():
    text = "hello world"
    truncated, was_truncated = truncate_output(text, max_bytes=1024)
    assert truncated == text
    assert was_truncated is False


def test_should_return_input_unchanged_when_exactly_at_limit():
    text = "x" * 100
    truncated, was_truncated = truncate_output(text, max_bytes=100)
    assert truncated == text
    assert was_truncated is False


def test_should_truncate_when_over_limit():
    text = "x" * 200
    truncated, was_truncated = truncate_output(text, max_bytes=100)
    assert was_truncated is True
    assert len(truncated) <= 200  # original head + marker
    assert "truncated" in truncated
    assert truncated.startswith("x" * 100)


def test_should_include_dropped_byte_count_in_marker():
    text = "x" * 250
    truncated, was_truncated = truncate_output(text, max_bytes=100)
    assert was_truncated is True
    assert "150" in truncated  # 250 - 100 = 150 dropped


def test_should_handle_empty_string():
    truncated, was_truncated = truncate_output("", max_bytes=100)
    assert truncated == ""
    assert was_truncated is False


def test_should_handle_unicode_safely():
    # 4-byte emojis should still be truncated by character count safely.
    text = "héllo " * 1000
    truncated, was_truncated = truncate_output(text, max_bytes=50)
    assert was_truncated is True
    assert "truncated" in truncated
