"""Tests for Server-Sent Events (SSE) formatting helpers."""

import json

from langflow.agentic.helpers.sse import (
    format_complete_event,
    format_error_event,
    format_progress_event,
    format_token_event,
)


class TestFormatProgressEvent:
    """Tests for format_progress_event function."""

    def test_should_format_generating_step_correctly(self):
        result = format_progress_event("generating", 1, 4)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        data = json.loads(result[6:-2])
        assert data["event"] == "progress"
        assert data["step"] == "generating"
        assert data["attempt"] == 1
        assert data["max_attempts"] == 4

    def test_should_format_validating_step_correctly(self):
        result = format_progress_event("validating", 2, 4)

        data = json.loads(result[6:-2])
        assert data["step"] == "validating"
        assert data["attempt"] == 2
        assert data["max_attempts"] == 4

    def test_should_format_validated_step_correctly(self):
        result = format_progress_event("validated", 1, 3)

        data = json.loads(result[6:-2])
        assert data["step"] == "validated"

    def test_should_format_validation_failed_step_correctly(self):
        result = format_progress_event("validation_failed", 2, 3)

        data = json.loads(result[6:-2])
        assert data["step"] == "validation_failed"

    def test_should_format_retrying_step_correctly(self):
        result = format_progress_event("retrying", 1, 3)

        data = json.loads(result[6:-2])
        assert data["step"] == "retrying"

    def test_should_include_message_when_provided(self):
        result = format_progress_event("generating", 1, 4, message="Generating response...")

        data = json.loads(result[6:-2])
        assert data["message"] == "Generating response..."

    def test_should_include_error_when_provided(self):
        result = format_progress_event("validation_failed", 1, 3, error="SyntaxError: invalid syntax")

        data = json.loads(result[6:-2])
        assert data["error"] == "SyntaxError: invalid syntax"

    def test_should_include_class_name_when_provided(self):
        result = format_progress_event("validated", 1, 3, class_name="MyComponent")

        data = json.loads(result[6:-2])
        assert data["class_name"] == "MyComponent"

    def test_should_include_component_code_when_provided(self):
        component_code = "class MyComponent: pass"
        result = format_progress_event("validation_failed", 1, 3, component_code=component_code)

        data = json.loads(result[6:-2])
        assert data["component_code"] == component_code

    def test_should_include_all_optional_fields_when_provided(self):
        result = format_progress_event(
            "validation_failed",
            2,
            4,
            message="Validation failed",
            error="SyntaxError",
            class_name="BrokenComponent",
            component_code="class BrokenComponent: pass",
        )

        data = json.loads(result[6:-2])
        assert data["message"] == "Validation failed"
        assert data["error"] == "SyntaxError"
        assert data["class_name"] == "BrokenComponent"
        assert data["component_code"] == "class BrokenComponent: pass"

    def test_should_not_include_optional_fields_when_not_provided(self):
        result = format_progress_event("generating", 1, 3)

        data = json.loads(result[6:-2])
        assert "message" not in data
        assert "error" not in data
        assert "class_name" not in data
        assert "component_code" not in data


class TestFormatCompleteEvent:
    """Tests for format_complete_event function."""

    def test_should_format_complete_event_correctly(self):
        test_data = {"result": "test", "validated": True}

        result = format_complete_event(test_data)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])
        assert parsed["event"] == "complete"
        assert parsed["data"]["result"] == "test"
        assert parsed["data"]["validated"] is True

    def test_should_handle_complex_data(self):
        test_data = {
            "result": "Component created",
            "validated": True,
            "class_name": "HelloWorldComponent",
            "component_code": "class HelloWorldComponent: pass",
            "validation_attempts": 1,
        }

        result = format_complete_event(test_data)

        parsed = json.loads(result[6:-2])
        assert parsed["data"]["class_name"] == "HelloWorldComponent"
        assert parsed["data"]["validation_attempts"] == 1

    def test_should_handle_empty_data(self):
        result = format_complete_event({})

        parsed = json.loads(result[6:-2])
        assert parsed["event"] == "complete"
        assert parsed["data"] == {}

    def test_should_handle_nested_data(self):
        test_data = {"nested": {"level1": {"level2": "value"}}}

        result = format_complete_event(test_data)

        parsed = json.loads(result[6:-2])
        assert parsed["data"]["nested"]["level1"]["level2"] == "value"


class TestFormatErrorEvent:
    """Tests for format_error_event function."""

    def test_should_format_error_event_correctly(self):
        result = format_error_event("Rate limit exceeded")

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])
        assert parsed["event"] == "error"
        assert parsed["message"] == "Rate limit exceeded"

    def test_should_handle_empty_message(self):
        result = format_error_event("")

        parsed = json.loads(result[6:-2])
        assert parsed["event"] == "error"
        assert parsed["message"] == ""

    def test_should_handle_special_characters_in_message(self):
        message = 'Error with "quotes" and <brackets>'

        result = format_error_event(message)

        parsed = json.loads(result[6:-2])
        assert parsed["message"] == message

    def test_should_handle_unicode_in_message(self):
        message = "Error with unicode: éàü 中文"

        result = format_error_event(message)

        parsed = json.loads(result[6:-2])
        assert parsed["message"] == message


class TestFormatTokenEvent:
    """Tests for format_token_event function."""

    def test_should_format_token_event_correctly(self):
        result = format_token_event("Hello")

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        parsed = json.loads(result[6:-2])
        assert parsed["event"] == "token"
        assert parsed["chunk"] == "Hello"

    def test_should_handle_empty_chunk(self):
        result = format_token_event("")

        parsed = json.loads(result[6:-2])
        assert parsed["chunk"] == ""

    def test_should_handle_whitespace_chunk(self):
        result = format_token_event("   ")

        parsed = json.loads(result[6:-2])
        assert parsed["chunk"] == "   "

    def test_should_handle_newline_in_chunk(self):
        result = format_token_event("line1\nline2")

        parsed = json.loads(result[6:-2])
        assert parsed["chunk"] == "line1\nline2"

    def test_should_handle_special_characters_in_chunk(self):
        chunk = 'Code: "class Foo"'

        result = format_token_event(chunk)

        parsed = json.loads(result[6:-2])
        assert parsed["chunk"] == chunk

    def test_should_handle_unicode_in_chunk(self):
        chunk = "Unicode: éàü 中文 😀"

        result = format_token_event(chunk)

        parsed = json.loads(result[6:-2])
        assert parsed["chunk"] == chunk


class TestSSEFormatting:
    """General SSE formatting tests."""

    def test_all_events_should_be_valid_sse_format(self):
        events = [
            format_progress_event("generating", 1, 3),
            format_complete_event({"result": "test"}),
            format_error_event("error"),
            format_token_event("chunk"),
        ]

        for event in events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")
            # Should be valid JSON after "data: " prefix
            json_str = event[6:-2]
            data = json.loads(json_str)
            assert "event" in data

    def test_events_should_be_parseable_as_json(self):
        events = [
            format_progress_event("validating", 2, 4, message="Testing"),
            format_complete_event({"key": "value"}),
            format_error_event("Test error"),
            format_token_event("Test chunk"),
        ]

        for event in events:
            json_str = event[6:-2]
            # Should not raise
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)
