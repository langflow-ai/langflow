"""Tests for MCP support utilities.

Tests the replace_none_and_null_with_empty_str function
which sanitizes data for MCP tool responses.
"""

from langflow.agentic.mcp.support import replace_none_and_null_with_empty_str

NOT_AVAIL = "Not available"


class TestReplaceNoneValues:
    """Tests for None value replacement."""

    def test_should_replace_none_with_not_available(self):
        """None values should become 'Not available'."""
        data = [{"key": None}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["key"] == NOT_AVAIL

    def test_should_replace_null_string_case_insensitive(self):
        """'null', 'NULL', 'Null' should all become 'Not available'."""
        data = [{"a": "null", "b": "NULL", "c": "Null"}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["a"] == NOT_AVAIL
        assert result[0]["b"] == NOT_AVAIL
        assert result[0]["c"] == NOT_AVAIL


class TestReplaceNanValues:
    """Tests for NaN and special float replacement."""

    def test_should_replace_nan_float(self):
        """float('nan') should become 'Not available'."""
        data = [{"val": float("nan")}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["val"] == NOT_AVAIL

    def test_should_replace_nan_string(self):
        """'nan' and 'NaN' strings should become 'Not available'."""
        data = [{"a": "nan", "b": "NaN"}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["a"] == NOT_AVAIL
        assert result[0]["b"] == NOT_AVAIL

    def test_should_replace_infinity_string(self):
        """'infinity' and '-infinity' strings should become 'Not available'."""
        data = [{"a": "infinity", "b": "-infinity", "c": "Infinity"}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["a"] == NOT_AVAIL
        assert result[0]["b"] == NOT_AVAIL
        assert result[0]["c"] == NOT_AVAIL


class TestNormalValues:
    """Tests that normal values are preserved."""

    def test_should_keep_normal_values(self):
        """Regular strings and numbers should remain unchanged."""
        data = [{"name": "test", "count": 42, "active": True}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["name"] == "test"
        assert result[0]["count"] == 42
        assert result[0]["active"] is True

    def test_should_keep_empty_string(self):
        """Empty string should remain as empty string (not 'null'-like)."""
        data = [{"val": ""}]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["val"] == ""


class TestRequiredFields:
    """Tests for required_fields parameter."""

    def test_should_add_missing_required_fields(self):
        """Missing required fields should be added with 'Not available'."""
        data = [{"name": "test"}]
        result = replace_none_and_null_with_empty_str(data, required_fields=["name", "email"])
        assert result[0]["name"] == "test"
        assert result[0]["email"] == NOT_AVAIL

    def test_should_handle_no_required_fields(self):
        """required_fields=None should not add extra fields."""
        data = [{"name": "test"}]
        result = replace_none_and_null_with_empty_str(data, required_fields=None)
        assert list(result[0].keys()) == ["name"]


class TestEdgeCases:
    """Tests for edge cases."""

    def test_should_handle_non_dict_items(self):
        """Non-dict items in the list should pass through unchanged."""
        data = ["string_item", 42, None]
        result = replace_none_and_null_with_empty_str(data)
        assert result == ["string_item", 42, None]

    def test_should_handle_empty_list(self):
        """Empty list should return empty list."""
        assert replace_none_and_null_with_empty_str([]) == []

    def test_should_handle_multiple_dicts(self):
        """Should process all dicts in the list."""
        data = [
            {"a": None, "b": "hello"},
            {"c": "null", "d": 10},
        ]
        result = replace_none_and_null_with_empty_str(data)
        assert result[0]["a"] == NOT_AVAIL
        assert result[0]["b"] == "hello"
        assert result[1]["c"] == NOT_AVAIL
        assert result[1]["d"] == 10
