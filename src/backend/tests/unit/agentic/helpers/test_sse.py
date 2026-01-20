"""Tests for SSE (Server-Sent Events) formatting helpers.

Tests the event formatting functions used for streaming responses.
"""

import json

import pytest
from langflow.agentic.helpers.sse import (
    format_complete_event,
    format_error_event,
    format_progress_event,
    format_token_event,
)


class TestFormatProgressEvent:
    """Tests for format_progress_event function."""

    def test_should_format_basic_progress_event(self):
        """Should format a basic progress event correctly."""
        result = format_progress_event("generating", 1, 4)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["event"] == "progress"
        assert data["step"] == "generating"
        assert data["attempt"] == 1
        assert data["max_attempts"] == 4

    def test_should_include_optional_message(self):
        """Should include optional message when provided."""
        result = format_progress_event("validating", 2, 3, message="Validating component...")

        data = json.loads(result[6:-2])

        assert data["message"] == "Validating component..."

    def test_should_include_optional_error(self):
        """Should include optional error when provided."""
        result = format_progress_event("validation_failed", 1, 3, error="SyntaxError: invalid syntax")

        data = json.loads(result[6:-2])

        assert data["error"] == "SyntaxError: invalid syntax"

    def test_should_include_optional_class_name(self):
        """Should include optional class_name when provided."""
        result = format_progress_event("validated", 1, 3, class_name="MyComponent")

        data = json.loads(result[6:-2])

        assert data["class_name"] == "MyComponent"

    def test_should_include_optional_component_code(self):
        """Should include optional component_code when provided."""
        code = "class Test(Component): pass"
        result = format_progress_event("validation_failed", 1, 3, component_code=code)

        data = json.loads(result[6:-2])

        assert data["component_code"] == code

    def test_should_include_all_optional_fields(self):
        """Should include all optional fields when provided."""
        result = format_progress_event(
            "validation_failed",
            2,
            4,
            message="Validation failed",
            error="SyntaxError",
            class_name="BrokenComponent",
            component_code="class Broken: pass",
        )

        data = json.loads(result[6:-2])

        assert data["event"] == "progress"
        assert data["step"] == "validation_failed"
        assert data["attempt"] == 2
        assert data["max_attempts"] == 4
        assert data["message"] == "Validation failed"
        assert data["error"] == "SyntaxError"
        assert data["class_name"] == "BrokenComponent"
        assert data["component_code"] == "class Broken: pass"

    def test_should_omit_none_optional_fields(self):
        """Should not include optional fields when they are None."""
        result = format_progress_event("generating", 1, 3)

        data = json.loads(result[6:-2])

        assert "message" not in data
        assert "error" not in data
        assert "class_name" not in data
        assert "component_code" not in data

    @pytest.mark.parametrize(
        "step",
        [
            "generating",
            "generation_complete",
            "extracting_code",
            "validating",
            "validated",
            "validation_failed",
            "retrying",
        ],
    )
    def test_should_accept_all_valid_step_types(self, step: str):
        """Should accept all valid step types."""
        result = format_progress_event(step, 1, 3)

        data = json.loads(result[6:-2])

        assert data["step"] == step


class TestFormatCompleteEvent:
    """Tests for format_complete_event function."""

    def test_should_format_complete_event_with_data(self):
        """Should format complete event with provided data."""
        test_data = {"result": "test", "validated": True, "class_name": "TestComponent"}
        result = format_complete_event(test_data)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "complete"
        assert parsed["data"] == test_data

    def test_should_format_complete_event_with_empty_data(self):
        """Should format complete event with empty data dict."""
        result = format_complete_event({})

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "complete"
        assert parsed["data"] == {}

    def test_should_preserve_nested_data_structure(self):
        """Should preserve nested data structures."""
        nested_data = {
            "result": "success",
            "metadata": {"attempts": 3, "duration": 1.5},
            "items": [1, 2, 3],
        }
        result = format_complete_event(nested_data)

        parsed = json.loads(result[6:-2])

        assert parsed["data"]["metadata"]["attempts"] == 3
        assert parsed["data"]["items"] == [1, 2, 3]


class TestFormatErrorEvent:
    """Tests for format_error_event function."""

    def test_should_format_error_event_with_message(self):
        """Should format error event with provided message."""
        result = format_error_event("Rate limit exceeded")

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "error"
        assert parsed["message"] == "Rate limit exceeded"

    def test_should_format_error_event_with_empty_message(self):
        """Should format error event with empty message."""
        result = format_error_event("")

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "error"
        assert parsed["message"] == ""

    def test_should_preserve_special_characters_in_message(self):
        """Should preserve special characters in error message."""
        message = 'Error: "invalid" <syntax> & issues'
        result = format_error_event(message)

        parsed = json.loads(result[6:-2])

        assert parsed["message"] == message


class TestFormatTokenEvent:
    """Tests for format_token_event function."""

    def test_should_format_token_event_with_chunk(self):
        """Should format token event with provided chunk."""
        result = format_token_event("Hello")

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "token"
        assert parsed["chunk"] == "Hello"

    def test_should_format_token_event_with_empty_chunk(self):
        """Should format token event with empty chunk."""
        result = format_token_event("")

        parsed = json.loads(result[6:-2])

        assert parsed["event"] == "token"
        assert parsed["chunk"] == ""

    def test_should_preserve_whitespace_in_chunk(self):
        """Should preserve whitespace in token chunk."""
        result = format_token_event("  hello  world  ")

        parsed = json.loads(result[6:-2])

        assert parsed["chunk"] == "  hello  world  "

    def test_should_preserve_newlines_in_chunk(self):
        """Should preserve newlines in token chunk."""
        result = format_token_event("line1\nline2\n")

        parsed = json.loads(result[6:-2])

        assert parsed["chunk"] == "line1\nline2\n"

    def test_should_handle_unicode_in_chunk(self):
        """Should handle unicode characters in chunk."""
        result = format_token_event("Hello 世界 🌍")

        parsed = json.loads(result[6:-2])

        assert parsed["chunk"] == "Hello 世界 🌍"


class TestSSEFormatConsistency:
    """Tests for SSE format consistency across all event types."""

    def test_all_events_should_have_consistent_format(self):
        """All events should have consistent SSE format."""
        events = [
            format_progress_event("generating", 1, 3),
            format_complete_event({"result": "test"}),
            format_error_event("error"),
            format_token_event("chunk"),
        ]

        for event in events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")
            # Should be valid JSON between "data: " and "\n\n"
            json_str = event[6:-2]
            parsed = json.loads(json_str)
            assert "event" in parsed

    def test_events_should_produce_valid_json(self):
        """All events should produce valid JSON."""
        test_cases = [
            format_progress_event("validating", 2, 4, message="Testing"),
            format_complete_event({"complex": {"nested": [1, 2, 3]}}),
            format_error_event("Test error with 'quotes' and \"double quotes\""),
            format_token_event("Token with special chars: <>&"),
        ]

        for event in test_cases:
            json_str = event[6:-2]
            # Should not raise
            json.loads(json_str)
