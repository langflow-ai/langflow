"""Unit tests for Agentics schema builder helper."""

from __future__ import annotations

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

from lfx.components.agentics.helpers.schema_builder import build_schema_fields


@pytest.mark.unit
class TestBuildSchemaFields:
    """Tests for build_schema_fields function."""

    def test_should_return_empty_list_when_fields_empty(self):
        """Test that empty input returns empty list."""
        result = build_schema_fields([])
        assert result == []

    def test_should_convert_single_field_to_tuple(self):
        """Test conversion of a single field definition."""
        fields = [
            {
                "name": "text",
                "description": "A text field",
                "type": "str",
                "multiple": False,
            }
        ]

        result = build_schema_fields(fields)

        assert len(result) == 1
        assert result[0] == ("text", "A text field", "str", False)

    def test_should_convert_multiple_fields_to_tuples(self):
        """Test conversion of multiple field definitions."""
        fields = [
            {"name": "name", "description": "User name", "type": "str", "multiple": False},
            {"name": "age", "description": "User age", "type": "int", "multiple": False},
            {"name": "active", "description": "Is active", "type": "bool", "multiple": False},
        ]

        result = build_schema_fields(fields)

        assert len(result) == 3
        assert result[0] == ("name", "User name", "str", False)
        assert result[1] == ("age", "User age", "int", False)
        assert result[2] == ("active", "Is active", "bool", False)

    def test_should_convert_list_type_when_multiple_is_true(self):
        """Test that multiple=True converts type to list[type]."""
        fields = [
            {"name": "tags", "description": "Tag list", "type": "str", "multiple": True},
        ]

        result = build_schema_fields(fields)

        assert len(result) == 1
        assert result[0] == ("tags", "Tag list", "list[str]", False)

    def test_should_handle_mixed_multiple_values(self):
        """Test handling fields with mixed multiple values."""
        fields = [
            {"name": "name", "description": "Single name", "type": "str", "multiple": False},
            {"name": "tags", "description": "Multiple tags", "type": "str", "multiple": True},
            {"name": "scores", "description": "Multiple scores", "type": "float", "multiple": True},
            {"name": "active", "description": "Single bool", "type": "bool", "multiple": False},
        ]

        result = build_schema_fields(fields)

        assert len(result) == 4
        assert result[0][2] == "str"
        assert result[1][2] == "list[str]"
        assert result[2][2] == "list[float]"
        assert result[3][2] == "bool"

    def test_should_handle_empty_description(self):
        """Test handling fields with empty description."""
        fields = [
            {"name": "field1", "description": "", "type": "str", "multiple": False},
        ]

        result = build_schema_fields(fields)

        assert result[0] == ("field1", "", "str", False)

    def test_should_handle_dict_type(self):
        """Test handling dict type fields."""
        fields = [
            {"name": "metadata", "description": "Metadata dict", "type": "dict", "multiple": False},
            {"name": "items", "description": "List of dicts", "type": "dict", "multiple": True},
        ]

        result = build_schema_fields(fields)

        assert result[0][2] == "dict"
        assert result[1][2] == "list[dict]"

    def test_should_always_set_required_to_false(self):
        """Test that required (4th element) is always False."""
        fields = [
            {"name": "field1", "description": "Desc 1", "type": "str", "multiple": False},
            {"name": "field2", "description": "Desc 2", "type": "int", "multiple": True},
        ]

        result = build_schema_fields(fields)

        for field_tuple in result:
            assert field_tuple[3] is False
