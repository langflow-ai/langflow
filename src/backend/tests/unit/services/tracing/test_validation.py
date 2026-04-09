"""Unit tests for langflow.services.tracing.validation.

Covers sanitize_query_string: happy path, edge cases, adversarial inputs.
"""

from __future__ import annotations

from langflow.services.tracing.validation import sanitize_query_string


class TestSanitizeQueryString:
    def test_should_return_none_for_none_input(self):
        assert sanitize_query_string(None) is None

    def test_should_return_plain_ascii_string_unchanged(self):
        assert sanitize_query_string("hello") == "hello"

    def test_should_return_alphanumeric_with_spaces(self):
        assert sanitize_query_string("my flow 123") == "my flow 123"

    def test_should_allow_printable_punctuation(self):
        result = sanitize_query_string("flow-name_v2.0")
        assert result == "flow-name_v2.0"

    def test_should_truncate_to_default_max_len_of_50(self):
        long_input = "a" * 60
        result = sanitize_query_string(long_input)
        assert result is not None
        assert len(result) == 50

    def test_should_truncate_to_custom_max_len(self):
        result = sanitize_query_string("abcdefghij", max_len=5)
        assert result == "abcde"

    def test_should_strip_leading_and_trailing_whitespace(self):
        assert sanitize_query_string("  hello  ") == "hello"

    def test_should_return_none_for_empty_string(self):
        assert sanitize_query_string("") is None

    def test_should_return_none_for_whitespace_only_string(self):
        assert sanitize_query_string("   ") is None

    def test_should_return_none_for_tab_only_string(self):
        assert sanitize_query_string("\t\t\t") is None

    def test_should_strip_non_printable_control_characters(self):
        result = sanitize_query_string("hello\x00world\n")
        assert result == "helloworld"

    def test_should_strip_delete_character(self):
        result = sanitize_query_string("hello\x7fworld")
        assert result == "helloworld"

    def test_should_strip_high_unicode_characters(self):
        result = sanitize_query_string("caf\u00e9")  # café
        assert result == "caf"

    def test_should_strip_emoji(self):
        result = sanitize_query_string("hello \U0001f600")
        assert result == "hello"

    def test_should_return_none_when_all_chars_stripped(self):
        result = sanitize_query_string("\x00\x01\x02")
        assert result is None

    def test_should_preserve_tilde_as_last_printable_ascii(self):
        assert sanitize_query_string("~") == "~"

    def test_should_preserve_space_as_first_printable_ascii(self):
        assert sanitize_query_string(" a ") == "a"

    def test_should_handle_exactly_max_len_input(self):
        exact = "a" * 50
        result = sanitize_query_string(exact)
        assert result == exact

    def test_should_handle_max_len_of_zero(self):
        result = sanitize_query_string("hello", max_len=0)
        assert result is None or result == ""

    def test_should_handle_mixed_printable_and_non_printable(self):
        result = sanitize_query_string("a\x00b\x01c")
        assert result == "abc"

    def test_should_strip_sql_injection_newlines(self):
        """Newlines used in SQL injection attempts are stripped."""
        result = sanitize_query_string("'; DROP TABLE traces;\n--")
        assert "\n" not in (result or "")

    def test_should_strip_null_byte_injection(self):
        result = sanitize_query_string("admin\x00extra")
        assert "\x00" not in (result or "")

    def test_should_truncate_after_stripping_not_before(self):
        """Truncation applies to the cleaned string, not the raw input."""
        # 10 non-printable chars + 3 printable chars; max_len=2 → "ab"
        raw = "\x00" * 10 + "abc"
        result = sanitize_query_string(raw, max_len=2)
        assert result == "ab"
