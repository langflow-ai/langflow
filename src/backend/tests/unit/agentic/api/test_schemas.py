"""Tests for API schemas.

Tests the Pydantic models used for request/response validation.
"""

import pytest
from langflow.agentic.api.schemas import AssistantRequest, StepType, ValidationResult
from pydantic import ValidationError


class TestAssistantRequest:
    """Tests for AssistantRequest schema."""

    def test_should_create_with_required_field_only(self):
        """Should create request with only required flow_id field."""
        request = AssistantRequest(flow_id="test-flow-id")

        assert request.flow_id == "test-flow-id"
        assert request.component_id is None
        assert request.field_name is None
        assert request.input_value is None
        assert request.max_retries is None
        assert request.model_name is None
        assert request.provider is None
        assert request.session_id is None

    def test_should_create_with_all_fields(self):
        """Should create request with all fields populated."""
        request = AssistantRequest(
            flow_id="flow-123",
            component_id="comp-456",
            field_name="input_field",
            input_value="Hello, world!",
            max_retries=5,
            model_name="gpt-4",
            provider="OpenAI",
            session_id="session-789",
        )

        assert request.flow_id == "flow-123"
        assert request.component_id == "comp-456"
        assert request.field_name == "input_field"
        assert request.input_value == "Hello, world!"
        assert request.max_retries == 5
        assert request.model_name == "gpt-4"
        assert request.provider == "OpenAI"
        assert request.session_id == "session-789"

    def test_should_raise_error_for_missing_flow_id(self):
        """Should raise validation error when flow_id is missing."""
        with pytest.raises(ValidationError) as exc_info:
            AssistantRequest()

        assert "flow_id" in str(exc_info.value)

    def test_should_accept_empty_string_for_optional_fields(self):
        """Should accept empty string for optional string fields."""
        request = AssistantRequest(
            flow_id="test",
            input_value="",
            component_id="",
        )

        assert request.input_value == ""
        assert request.component_id == ""

    def test_should_serialize_to_dict(self):
        """Should serialize to dictionary correctly."""
        request = AssistantRequest(
            flow_id="test-flow",
            max_retries=3,
            provider="Anthropic",
        )

        data = request.model_dump()

        assert data["flow_id"] == "test-flow"
        assert data["max_retries"] == 3
        assert data["provider"] == "Anthropic"
        assert data["component_id"] is None

    def test_should_deserialize_from_dict(self):
        """Should deserialize from dictionary correctly."""
        data = {
            "flow_id": "test-flow",
            "input_value": "test input",
            "max_retries": 2,
        }

        request = AssistantRequest(**data)

        assert request.flow_id == "test-flow"
        assert request.input_value == "test input"
        assert request.max_retries == 2


class TestValidationResult:
    """Tests for ValidationResult schema."""

    def test_should_create_valid_result(self):
        """Should create a valid validation result."""
        result = ValidationResult(
            is_valid=True,
            code="class MyComponent(Component): pass",
            class_name="MyComponent",
        )

        assert result.is_valid is True
        assert result.code == "class MyComponent(Component): pass"
        assert result.class_name == "MyComponent"
        assert result.error is None

    def test_should_create_invalid_result_with_error(self):
        """Should create an invalid validation result with error."""
        result = ValidationResult(
            is_valid=False,
            code="class Broken(Component)",
            error="SyntaxError: expected ':'",
            class_name="Broken",
        )

        assert result.is_valid is False
        assert result.error == "SyntaxError: expected ':'"
        assert result.class_name == "Broken"

    def test_should_create_with_required_field_only(self):
        """Should create with only required is_valid field."""
        result = ValidationResult(is_valid=False)

        assert result.is_valid is False
        assert result.code is None
        assert result.error is None
        assert result.class_name is None

    def test_should_serialize_to_dict(self):
        """Should serialize to dictionary correctly."""
        result = ValidationResult(
            is_valid=True,
            code="test code",
            class_name="TestComponent",
        )

        data = result.model_dump()

        assert data["is_valid"] is True
        assert data["code"] == "test code"
        assert data["class_name"] == "TestComponent"
        assert data["error"] is None

    def test_should_deserialize_from_dict(self):
        """Should deserialize from dictionary correctly."""
        data = {
            "is_valid": False,
            "error": "Test error",
        }

        result = ValidationResult(**data)

        assert result.is_valid is False
        assert result.error == "Test error"


class TestStepType:
    """Tests for StepType literal type."""

    def test_should_define_all_expected_step_types(self):
        """Should define all expected step types."""
        expected_steps = [
            "generating",
            "generation_complete",
            "extracting_code",
            "validating",
            "validated",
            "validation_failed",
            "retrying",
        ]

        # StepType is a Literal, we can check its args
        step_type_args = StepType.__args__

        for step in expected_steps:
            assert step in step_type_args, f"Missing step type: {step}"

    def test_step_types_should_be_strings(self):
        """All step types should be strings."""
        for step in StepType.__args__:
            assert isinstance(step, str)


class TestSchemaIntegration:
    """Integration tests for schema interactions."""

    def test_assistant_request_json_round_trip(self):
        """Should survive JSON serialization round trip."""
        original = AssistantRequest(
            flow_id="test-flow",
            component_id="comp-1",
            input_value="test",
            max_retries=3,
        )

        json_str = original.model_dump_json()
        restored = AssistantRequest.model_validate_json(json_str)

        assert restored.flow_id == original.flow_id
        assert restored.component_id == original.component_id
        assert restored.input_value == original.input_value
        assert restored.max_retries == original.max_retries

    def test_validation_result_json_round_trip(self):
        """Should survive JSON serialization round trip."""
        original = ValidationResult(
            is_valid=True,
            code="class Test: pass",
            class_name="Test",
        )

        json_str = original.model_dump_json()
        restored = ValidationResult.model_validate_json(json_str)

        assert restored.is_valid == original.is_valid
        assert restored.code == original.code
        assert restored.class_name == original.class_name
