"""Tests for extract_json_from_text — extracts a JSON value embedded in arbitrary text."""

from __future__ import annotations

import pytest
from lfx.components.models_and_agents.structured_output.json_extraction import (
    extract_json_from_text,
)


@pytest.mark.unit
class TestExtractJsonFromText:
    def test_should_return_dict_when_text_is_pure_json_object(self):
        text = '{"foo": "bar"}'

        assert extract_json_from_text(text) == {"foo": "bar"}

    def test_should_return_first_object_when_text_contains_prose_around_json(self):
        text = 'Here is the answer: {"foo": "bar"} — hope it helps.'

        assert extract_json_from_text(text) == {"foo": "bar"}

    def test_should_return_object_with_nested_keys_when_json_is_nested(self):
        text = 'Result: {"outer": {"inner": [1, 2, 3]}}'

        assert extract_json_from_text(text) == {"outer": {"inner": [1, 2, 3]}}

    def test_should_extract_object_when_wrapped_in_markdown_code_fence(self):
        text = '```json\n{"key": "value"}\n```'

        assert extract_json_from_text(text) == {"key": "value"}

    def test_should_return_none_when_no_json_object_present(self):
        text = "This response has no structured payload at all."

        assert extract_json_from_text(text) is None

    def test_should_return_none_when_json_braces_are_unbalanced(self):
        text = "almost JSON: {unbalanced braces here {"

        assert extract_json_from_text(text) is None

    def test_should_return_list_when_text_is_pure_json_array(self):
        text = '[{"a": 1}, {"a": 2}]'

        assert extract_json_from_text(text) == [{"a": 1}, {"a": 2}]
