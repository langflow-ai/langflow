"""Tests for the schema builder helper that converts field definitions to Pydantic model tuples."""

from __future__ import annotations

import pytest
from lfx.components.agentics.helpers.schema_builder import build_schema_fields


class TestBuildSchemaFields:
    """Tests for build_schema_fields function."""

    def test_should_convert_single_string_field(self):
        # Arrange
        fields = [{"name": "title", "description": "A short title", "type": "str", "multiple": False}]

        # Act
        result = build_schema_fields(fields)

        # Assert
        assert result == [("title", "A short title", "str", False)]

    def test_should_convert_multiple_fields_preserving_order(self):
        # Arrange
        fields = [
            {"name": "name", "description": "Person name", "type": "str", "multiple": False},
            {"name": "age", "description": "Person age", "type": "int", "multiple": False},
            {"name": "score", "description": "Rating score", "type": "float", "multiple": False},
        ]

        # Act
        result = build_schema_fields(fields)

        # Assert
        assert len(result) == 3
        assert result[0] == ("name", "Person name", "str", False)
        assert result[1] == ("age", "Person age", "int", False)
        assert result[2] == ("score", "Rating score", "float", False)

    def test_should_wrap_type_in_list_when_multiple_is_true(self):
        # Arrange
        fields = [{"name": "tags", "description": "Tag list", "type": "str", "multiple": True}]

        # Act
        result = build_schema_fields(fields)

        # Assert
        assert result == [("tags", "Tag list", "list[str]", False)]

    def test_should_handle_all_supported_types(self):
        # Arrange
        supported_types = ["str", "int", "float", "bool", "dict"]
        fields = [
            {"name": f"field_{t}", "description": f"A {t} field", "type": t, "multiple": False} for t in supported_types
        ]

        # Act
        result = build_schema_fields(fields)

        # Assert
        for i, field_type in enumerate(supported_types):
            assert result[i][2] == field_type

    def test_should_return_empty_list_for_empty_input(self):
        # Act
        result = build_schema_fields([])

        # Assert
        assert result == []

    def test_should_wrap_dict_type_in_list_when_multiple(self):
        # Arrange
        fields = [{"name": "metadata", "description": "Metadata entries", "type": "dict", "multiple": True}]

        # Act
        result = build_schema_fields(fields)

        # Assert
        assert result == [("metadata", "Metadata entries", "list[dict]", False)]

    def test_should_always_set_required_to_false(self):
        # Arrange
        fields = [
            {"name": "a", "description": "First", "type": "str", "multiple": False},
            {"name": "b", "description": "Second", "type": "int", "multiple": True},
        ]

        # Act
        result = build_schema_fields(fields)

        # Assert
        assert all(field[3] is False for field in result)

    def test_should_raise_key_error_when_field_missing_required_key(self):
        # Arrange - missing "type" key
        fields = [{"name": "broken", "description": "No type"}]

        # Act & Assert
        with pytest.raises(KeyError):
            build_schema_fields(fields)
