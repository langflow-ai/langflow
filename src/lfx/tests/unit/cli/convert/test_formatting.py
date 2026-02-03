"""Unit tests for the formatting module."""

from __future__ import annotations

from lfx.cli.convert.formatting import format_value


class TestFormatValue:
    """Tests for format_value function."""

    def test_should_format_simple_string(self) -> None:
        """Test formatting a simple string."""
        result = format_value("hello")
        assert result == "'hello'"

    def test_should_format_string_with_single_quotes(self) -> None:
        """Test formatting a string containing single quotes."""
        result = format_value("it's a test")
        assert result == '"it\'s a test"'

    def test_should_format_multiline_string_as_triple_quoted(self) -> None:
        """Test formatting a multiline string uses triple quotes."""
        result = format_value("line1\nline2")
        assert result.startswith('"""')
        assert result.endswith('"""')
        assert "line1" in result
        assert "line2" in result

    def test_should_format_long_string_as_triple_quoted(self) -> None:
        """Test formatting a string longer than 80 chars uses triple quotes."""
        long_string = "a" * 100
        result = format_value(long_string)
        assert result.startswith('"""')
        assert result.endswith('"""')

    def test_should_return_variable_reference_for_dollar_prefix(self) -> None:
        """Test that strings starting with $ are returned as variable references."""
        result = format_value("$MY_VARIABLE")
        assert result == "MY_VARIABLE"

    def test_should_format_boolean_true(self) -> None:
        """Test formatting boolean True."""
        bool_true: bool = True
        result = format_value(bool_true)
        assert result == "True"

    def test_should_format_boolean_false(self) -> None:
        """Test formatting boolean False."""
        bool_false: bool = False
        result = format_value(bool_false)
        assert result == "False"

    def test_should_format_integer(self) -> None:
        """Test formatting an integer."""
        result = format_value(42)
        assert result == "42"

    def test_should_format_float(self) -> None:
        """Test formatting a float."""
        result = format_value(3.14)
        assert result == "3.14"

    def test_should_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        result = format_value([])
        assert result == "[]"

    def test_should_format_single_item_list_inline(self) -> None:
        """Test formatting a single-item list."""
        result = format_value(["item"])
        assert result == "['item']"

    def test_should_format_multi_item_list_with_newlines(self) -> None:
        """Test formatting a multi-item list with proper indentation."""
        result = format_value(["item1", "item2", "item3"])
        assert "'item1'" in result
        assert "'item2'" in result
        assert "'item3'" in result

    def test_should_format_empty_dict(self) -> None:
        """Test formatting an empty dict."""
        result = format_value({})
        assert result == "{}"

    def test_should_format_small_dict_inline(self) -> None:
        """Test formatting a small dict inline."""
        result = format_value({"key": "value"})
        assert "'key': 'value'" in result

    def test_should_format_nested_structures(self) -> None:
        """Test formatting nested lists and dicts."""
        result = format_value({"list": [1, 2, 3], "nested": {"a": "b"}})
        assert "'list'" in result
        assert "'nested'" in result

    def test_should_escape_triple_quotes_in_multiline_string(self) -> None:
        """Test that triple quotes in content are escaped."""
        result = format_value('has """triple""" quotes\ninside')
        assert r"\"\"\"" in result
