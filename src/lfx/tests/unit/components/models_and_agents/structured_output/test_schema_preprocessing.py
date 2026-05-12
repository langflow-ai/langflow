"""Tests for preprocess_schema — normalizes TableInput rows for build_model_from_schema."""

from __future__ import annotations

import pytest
from lfx.components.models_and_agents.structured_output.schema_preprocessing import (
    preprocess_schema,
)


@pytest.mark.unit
class TestPreprocessSchema:
    def test_should_coerce_truthy_string_to_bool_when_multiple_is_string_yes(self):
        raw = [{"name": "tags", "type": "str", "description": "tags", "multiple": "yes"}]

        normalized = preprocess_schema(raw)

        assert normalized == [{"name": "tags", "type": "str", "description": "tags", "multiple": True}]

    @pytest.mark.parametrize("truthy", ["true", "True", "TRUE", "1", "t", "y", "yes", "YES"])
    def test_should_coerce_truthy_string_variants_to_bool_when_multiple_is_truthy(self, truthy):
        raw = [{"name": "f", "type": "str", "description": "", "multiple": truthy}]

        normalized = preprocess_schema(raw)

        assert normalized[0]["multiple"] is True

    @pytest.mark.parametrize("falsy", ["false", "False", "0", "no", "n", "", "anything-else"])
    def test_should_coerce_falsy_string_to_bool_when_multiple_is_not_truthy(self, falsy):
        raw = [{"name": "f", "type": "str", "description": "", "multiple": falsy}]

        normalized = preprocess_schema(raw)

        assert normalized[0]["multiple"] is False

    def test_should_preserve_bool_value_when_multiple_is_already_bool(self):
        raw = [
            {"name": "a", "type": "str", "description": "", "multiple": True},
            {"name": "b", "type": "str", "description": "", "multiple": False},
        ]

        normalized = preprocess_schema(raw)

        assert normalized[0]["multiple"] is True
        assert normalized[1]["multiple"] is False

    def test_should_default_missing_fields_when_schema_field_is_partial(self):
        raw = [{"name": "only_name"}]

        normalized = preprocess_schema(raw)

        assert normalized == [{"name": "only_name", "type": "str", "description": "", "multiple": False}]

    def test_should_default_name_when_field_has_no_name(self):
        raw = [{"type": "int"}]

        normalized = preprocess_schema(raw)

        assert normalized[0]["name"] == "field"
        assert normalized[0]["type"] == "int"

    def test_should_return_empty_list_when_input_is_empty(self):
        assert preprocess_schema([]) == []

    def test_should_coerce_non_string_name_to_string_when_input_is_int(self):
        raw = [{"name": 42, "type": "str"}]

        normalized = preprocess_schema(raw)

        assert normalized[0]["name"] == "42"
        assert isinstance(normalized[0]["name"], str)
