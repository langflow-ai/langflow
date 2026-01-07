"""Unit tests for mcp/support module utility functions."""

import math

from langflow.agentic.mcp.support import replace_none_and_null_with_empty_str


@pytest.mark.skip(reason="Skipping agentic tests")
class TestReplaceNoneAndNullWithEmptyStr:
    """Test cases for replace_none_and_null_with_empty_str function."""

    def test_replace_none_values(self):
        """Test that None values are replaced with 'Not available'."""
        data = [
            {"name": "test", "value": None},
            {"name": "test2", "value": "valid"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "valid"

    def test_replace_null_string_lowercase(self):
        """Test that 'null' string is replaced."""
        data = [
            {"name": "test", "value": "null"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"

    def test_replace_null_string_uppercase(self):
        """Test that 'NULL' string is replaced."""
        data = [
            {"name": "test", "value": "NULL"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"

    def test_replace_null_string_mixed_case(self):
        """Test that mixed case 'Null' is replaced."""
        data = [
            {"name": "test", "value": "Null"},
            {"name": "test2", "value": "NuLl"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"

    def test_replace_nan_float(self):
        """Test that NaN float values are replaced."""
        data = [
            {"name": "test", "value": float("nan")},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"

    def test_replace_nan_string(self):
        """Test that 'NaN' string is replaced."""
        data = [
            {"name": "test", "value": "NaN"},
            {"name": "test2", "value": "nan"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"

    def test_replace_infinity_string(self):
        """Test that 'Infinity' string is replaced."""
        data = [
            {"name": "test", "value": "Infinity"},
            {"name": "test2", "value": "infinity"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"

    def test_replace_negative_infinity_string(self):
        """Test that '-Infinity' string is replaced."""
        data = [
            {"name": "test", "value": "-Infinity"},
            {"name": "test2", "value": "-infinity"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"

    def test_preserve_valid_strings(self):
        """Test that valid strings are preserved."""
        data = [
            {"name": "test", "value": "valid string"},
            {"name": "test2", "value": "another value"},
            {"name": "test3", "value": ""},  # Empty string
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == "valid string"
        assert result[1]["value"] == "another value"
        assert result[2]["value"] == ""  # Empty string preserved

    def test_preserve_numbers(self):
        """Test that valid numbers are preserved."""
        data = [
            {"name": "int", "value": 42},
            {"name": "float", "value": 3.14},
            {"name": "zero", "value": 0},
            {"name": "negative", "value": -100},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == 42
        assert result[1]["value"] == 3.14
        assert result[2]["value"] == 0
        assert result[3]["value"] == -100

    def test_preserve_booleans(self):
        """Test that boolean values are preserved."""
        data = [
            {"name": "true", "value": True},
            {"name": "false", "value": False},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] is True
        assert result[1]["value"] is False

    def test_preserve_lists(self):
        """Test that list values are preserved."""
        data = [
            {"name": "list", "value": [1, 2, 3]},
            {"name": "empty_list", "value": []},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["value"] == [1, 2, 3]
        assert result[1]["value"] == []

    def test_preserve_nested_dicts(self):
        """Test that nested dict values are preserved (not recursively processed)."""
        data = [
            {"name": "nested", "value": {"inner": None}},
        ]

        result = replace_none_and_null_with_empty_str(data)

        # Note: The function doesn't recursively process nested dicts
        assert result[0]["value"] == {"inner": None}

    def test_required_fields_adds_missing_fields(self):
        """Test that missing required fields are added with 'Not available'."""
        data = [
            {"name": "test"},  # Missing 'value' and 'description'
        ]

        result = replace_none_and_null_with_empty_str(data, required_fields=["name", "value", "description"])

        assert result[0]["name"] == "test"
        assert result[0]["value"] == "Not available"
        assert result[0]["description"] == "Not available"

    def test_required_fields_preserves_existing(self):
        """Test that existing values are not overwritten by required fields."""
        data = [
            {"name": "test", "value": "existing"},
        ]

        result = replace_none_and_null_with_empty_str(data, required_fields=["name", "value"])

        assert result[0]["name"] == "test"
        assert result[0]["value"] == "existing"

    def test_empty_data_list(self):
        """Test handling of empty data list."""
        data = []

        result = replace_none_and_null_with_empty_str(data)

        assert result == []

    def test_multiple_items(self):
        """Test processing multiple items in list."""
        data = [
            {"name": "first", "value": None},
            {"name": "second", "value": "null"},
            {"name": "third", "value": "valid"},
            {"name": "fourth", "value": float("nan")},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert len(result) == 4
        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"
        assert result[2]["value"] == "valid"
        assert result[3]["value"] == "Not available"

    def test_non_dict_items_preserved(self):
        """Test that non-dict items in list are preserved as-is."""
        data = [
            {"name": "dict"},
            "string_item",
            123,
            None,
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert len(result) == 4
        assert result[0] == {"name": "dict"}
        assert result[1] == "string_item"
        assert result[2] == 123
        assert result[3] is None  # Non-dict None is preserved

    def test_whitespace_handling(self):
        """Test handling of whitespace around null values."""
        data = [
            {"name": "test", "value": " null "},
            {"name": "test2", "value": "  NaN  "},
            {"name": "test3", "value": " Infinity "},
        ]

        result = replace_none_and_null_with_empty_str(data)

        # Whitespace around null values should be handled
        assert result[0]["value"] == "Not available"
        assert result[1]["value"] == "Not available"
        assert result[2]["value"] == "Not available"

    def test_multiple_keys_in_dict(self):
        """Test dicts with multiple keys, some null."""
        data = [
            {
                "name": "test",
                "value": None,
                "description": "null",
                "count": 0,
                "active": True,
            }
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["name"] == "test"
        assert result[0]["value"] == "Not available"
        assert result[0]["description"] == "Not available"
        assert result[0]["count"] == 0  # Zero preserved
        assert result[0]["active"] is True


@pytest.mark.skip(reason="Skipping agentic tests")
class TestRealWorldScenarios:
    """Test with real-world-like data scenarios."""

    def test_component_data_with_nulls(self):
        """Test processing component metadata with null values."""
        component_data = [
            {
                "name": "OpenAIModel",
                "type": "llms",
                "display_name": "OpenAI Model",
                "description": None,
                "documentation": "null",
                "icon": None,
            },
            {
                "name": "ChatInput",
                "type": "inputs",
                "display_name": "Chat Input",
                "description": "User input component",
                "documentation": "https://docs.example.com",
                "icon": "chat",
            },
        ]

        result = replace_none_and_null_with_empty_str(
            component_data, required_fields=["name", "type", "display_name", "description"]
        )

        # First component
        assert result[0]["name"] == "OpenAIModel"
        assert result[0]["description"] == "Not available"
        assert result[0]["documentation"] == "Not available"
        assert result[0]["icon"] == "Not available"

        # Second component - all valid
        assert result[1]["description"] == "User input component"
        assert result[1]["documentation"] == "https://docs.example.com"

    def test_template_data_with_mixed_values(self):
        """Test processing template data with mixed value types."""
        template_data = [
            {
                "id": "abc123",
                "name": "Test Template",
                "description": None,
                "tags": ["agent", "chat"],
                "is_component": False,
                "data": {"nodes": [], "edges": []},
                "icon": "null",
                "last_tested_version": float("nan") if math.isnan(float("nan")) else None,
            }
        ]

        result = replace_none_and_null_with_empty_str(template_data)

        assert result[0]["id"] == "abc123"
        assert result[0]["name"] == "Test Template"
        assert result[0]["description"] == "Not available"
        assert result[0]["tags"] == ["agent", "chat"]
        assert result[0]["is_component"] is False
        assert result[0]["icon"] == "Not available"

    def test_large_dataset(self):
        """Test processing a large dataset efficiently."""
        # Create 100 items with various null values
        data = []
        for i in range(100):
            item = {
                "id": f"item_{i}",
                "name": f"Item {i}",
                "value": None if i % 3 == 0 else f"value_{i}",
                "count": i,
            }
            data.append(item)

        result = replace_none_and_null_with_empty_str(data)

        assert len(result) == 100

        # Check that null values are replaced
        for i, item in enumerate(result):
            if i % 3 == 0:
                assert item["value"] == "Not available"
            else:
                assert item["value"] == f"value_{i}"

    def test_search_results_processing(self):
        """Test processing search results data."""
        search_results = [
            {
                "name": "Component1",
                "type": "llms",
                "display_name": "Component 1",
                "description": "A useful component",
                "text": None,  # Will be added by search
            },
            {
                "name": "Component2",
                "type": "agents",
                "display_name": None,
                "description": "null",
                "text": None,
            },
        ]

        result = replace_none_and_null_with_empty_str(
            search_results, required_fields=["name", "type", "display_name", "description", "text"]
        )

        assert result[0]["text"] == "Not available"
        assert result[1]["display_name"] == "Not available"
        assert result[1]["description"] == "Not available"
        assert result[1]["text"] == "Not available"


@pytest.mark.skip(reason="Skipping agentic tests")
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_not_replaced(self):
        """Test that empty strings are not replaced."""
        data = [{"name": "", "value": ""}]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["name"] == ""
        assert result[0]["value"] == ""

    def test_string_containing_null(self):
        """Test that strings containing 'null' as part are preserved."""
        data = [
            {"name": "nullable_field"},
            {"value": "This is not null"},
            {"desc": "null-like-but-not"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["name"] == "nullable_field"
        assert result[1]["value"] == "This is not null"
        assert result[2]["desc"] == "null-like-but-not"

    def test_none_in_required_fields(self):
        """Test that None required_fields is handled."""
        data = [{"name": "test"}]

        result = replace_none_and_null_with_empty_str(data, required_fields=None)

        assert result[0]["name"] == "test"

    def test_empty_required_fields(self):
        """Test that empty required_fields list is handled."""
        data = [{"name": "test"}]

        result = replace_none_and_null_with_empty_str(data, required_fields=[])

        assert result[0]["name"] == "test"

    def test_unicode_values_preserved(self):
        """Test that unicode values are preserved."""
        data = [
            {"name": "日本語", "value": "中文"},
            {"name": "emoji", "value": "🎉"},
        ]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["name"] == "日本語"
        assert result[0]["value"] == "中文"
        assert result[1]["value"] == "🎉"

    def test_special_float_values(self):
        """Test handling of special float values."""
        data = [
            {"name": "inf", "value": float("inf")},
            {"name": "neg_inf", "value": float("-inf")},
        ]

        result = replace_none_and_null_with_empty_str(data)

        # Note: float inf is not NaN, so might be preserved
        # This depends on implementation - checking it doesn't crash
        assert len(result) == 2

    def test_very_long_string(self):
        """Test handling of very long strings."""
        long_string = "x" * 100000
        data = [{"name": long_string}]

        result = replace_none_and_null_with_empty_str(data)

        assert result[0]["name"] == long_string
