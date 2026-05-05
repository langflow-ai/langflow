"""Tests for parse_and_validate_fallback_content — the legacy regex+Pydantic path, demoted to fallback only."""

from __future__ import annotations

import pytest
from lfx.components.models_and_agents.structured_output.prompt_fallback_invoker import (
    parse_and_validate_fallback_content,
)
from pydantic import BaseModel


class _Person(BaseModel):
    name: str
    age: int


@pytest.mark.unit
class TestParseAndValidateFallbackContent:
    def test_should_return_validated_list_when_content_is_pure_json_object(self):
        content = '{"name": "Alice", "age": 30}'

        result = parse_and_validate_fallback_content(content, _Person)

        assert result == [{"name": "Alice", "age": 30}]

    def test_should_return_validated_list_when_content_has_prose_around_json(self):
        content = 'Sure! Here you go: {"name": "Bob", "age": 25}. Done.'

        result = parse_and_validate_fallback_content(content, _Person)

        assert result == [{"name": "Bob", "age": 25}]

    def test_should_return_list_of_validated_objects_when_content_is_json_array(self):
        content = '[{"name": "A", "age": 1}, {"name": "B", "age": 2}]'

        result = parse_and_validate_fallback_content(content, _Person)

        assert result == [{"name": "A", "age": 1}, {"name": "B", "age": 2}]

    def test_should_return_raw_json_when_output_model_is_none(self):
        content = '{"anything": "goes"}'

        result = parse_and_validate_fallback_content(content, output_model=None)

        assert result == {"anything": "goes"}

    def test_should_return_content_with_error_when_json_cannot_be_parsed(self):
        content = "no JSON whatsoever in this response"

        result = parse_and_validate_fallback_content(content, _Person)

        assert isinstance(result, dict)
        assert result["content"] == content
        assert "error" in result

    def test_should_attach_validation_error_when_payload_fails_schema(self):
        # Missing required field "age"
        content = '{"name": "Alice"}'

        result = parse_and_validate_fallback_content(content, _Person)

        assert isinstance(result, list)
        assert len(result) == 1
        assert "validation_error" in result[0]
        assert result[0]["data"] == {"name": "Alice"}

    def test_should_attach_validation_error_to_invalid_list_item_when_one_item_fails(self):
        content = '[{"name": "Good", "age": 1}, {"name": "BadOnly"}]'

        result = parse_and_validate_fallback_content(content, _Person)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"name": "Good", "age": 1}
        assert "validation_error" in result[1]
