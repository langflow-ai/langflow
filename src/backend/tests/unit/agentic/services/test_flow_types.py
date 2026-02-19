"""Tests for flow execution types and constants.

Tests the dataclasses and constants used in flow execution.
"""

from pathlib import Path

from langflow.agentic.services.flow_types import (
    FLOWS_BASE_PATH,
    LANGFLOW_ASSISTANT_FLOW,
    MAX_VALIDATION_RETRIES,
    STREAMING_EVENT_TIMEOUT_SECONDS,
    STREAMING_QUEUE_MAX_SIZE,
    TRANSLATION_FLOW,
    VALIDATION_RETRY_TEMPLATE,
    VALIDATION_UI_DELAY_SECONDS,
    FlowExecutionResult,
    IntentResult,
)


class TestFlowExecutionResult:
    """Tests for FlowExecutionResult dataclass."""

    def test_should_create_with_defaults(self):
        """Should create with empty result and no error by default."""
        result = FlowExecutionResult()

        assert result.result == {}
        assert result.error is None

    def test_should_detect_error_when_set(self):
        """Should return has_error=True when error is set."""
        result = FlowExecutionResult(error=ValueError("test error"))

        assert result.has_error is True
        assert result.has_result is False

    def test_should_detect_result_when_set(self):
        """Should return has_result=True when result is non-empty."""
        result = FlowExecutionResult(result={"key": "value"})

        assert result.has_result is True
        assert result.has_error is False

    def test_should_allow_both_result_and_error(self):
        """Should allow both result and error to be set simultaneously."""
        result = FlowExecutionResult(
            result={"partial": "data"},
            error=RuntimeError("partial failure"),
        )

        assert result.has_result is True
        assert result.has_error is True

    def test_should_return_false_for_empty_dict_result(self):
        """Should return has_result=False for empty dict."""
        result = FlowExecutionResult(result={})

        assert result.has_result is False

    def test_should_store_exception_details(self):
        """Should preserve exception details."""
        error = ValueError("detailed message")
        result = FlowExecutionResult(error=error)

        assert result.error is error
        assert str(result.error) == "detailed message"


class TestIntentResult:
    """Tests for IntentResult dataclass."""

    def test_should_create_with_translation_and_intent(self):
        """Should create with translation and intent fields."""
        result = IntentResult(translation="hello world", intent="question")

        assert result.translation == "hello world"
        assert result.intent == "question"

    def test_should_support_generate_component_intent(self):
        """Should support generate_component as valid intent value."""
        result = IntentResult(translation="create a component", intent="generate_component")

        assert result.intent == "generate_component"

    def test_should_be_equality_comparable(self):
        """Should support equality comparison."""
        result1 = IntentResult(translation="test", intent="question")
        result2 = IntentResult(translation="test", intent="question")
        result3 = IntentResult(translation="test", intent="generate_component")

        assert result1 == result2
        assert result1 != result3

    def test_should_allow_empty_translation(self):
        """Should allow empty string as translation."""
        result = IntentResult(translation="", intent="question")

        assert result.translation == ""


class TestConstants:
    """Tests for module constants."""

    def test_flows_base_path_should_exist(self):
        """FLOWS_BASE_PATH should be a valid path to flows directory."""
        assert isinstance(FLOWS_BASE_PATH, Path)
        assert FLOWS_BASE_PATH.name == "flows"

    def test_flows_base_path_parent_should_be_agentic(self):
        """FLOWS_BASE_PATH parent should be agentic directory."""
        assert FLOWS_BASE_PATH.parent.name == "agentic"

    def test_streaming_queue_max_size_should_be_positive(self):
        """STREAMING_QUEUE_MAX_SIZE should be a positive integer."""
        assert isinstance(STREAMING_QUEUE_MAX_SIZE, int)
        assert STREAMING_QUEUE_MAX_SIZE > 0

    def test_streaming_queue_max_size_should_be_reasonable(self):
        """STREAMING_QUEUE_MAX_SIZE should be within reasonable bounds."""
        assert STREAMING_QUEUE_MAX_SIZE >= 100
        assert STREAMING_QUEUE_MAX_SIZE <= 10000

    def test_streaming_timeout_should_be_positive(self):
        """STREAMING_EVENT_TIMEOUT_SECONDS should be positive."""
        assert isinstance(STREAMING_EVENT_TIMEOUT_SECONDS, float)
        assert STREAMING_EVENT_TIMEOUT_SECONDS > 0

    def test_streaming_timeout_should_be_reasonable(self):
        """STREAMING_EVENT_TIMEOUT_SECONDS should be within reasonable bounds."""
        assert STREAMING_EVENT_TIMEOUT_SECONDS >= 30
        assert STREAMING_EVENT_TIMEOUT_SECONDS <= 600

    def test_max_validation_retries_should_be_positive(self):
        """MAX_VALIDATION_RETRIES should be a positive integer."""
        assert isinstance(MAX_VALIDATION_RETRIES, int)
        assert MAX_VALIDATION_RETRIES > 0

    def test_max_validation_retries_should_be_reasonable(self):
        """MAX_VALIDATION_RETRIES should be within reasonable bounds."""
        assert MAX_VALIDATION_RETRIES >= 1
        assert MAX_VALIDATION_RETRIES <= 10

    def test_validation_ui_delay_should_be_small(self):
        """VALIDATION_UI_DELAY_SECONDS should be a small positive value."""
        assert isinstance(VALIDATION_UI_DELAY_SECONDS, float)
        assert VALIDATION_UI_DELAY_SECONDS > 0
        assert VALIDATION_UI_DELAY_SECONDS < 2

    def test_langflow_assistant_flow_should_be_string(self):
        """LANGFLOW_ASSISTANT_FLOW should be a non-empty string."""
        assert isinstance(LANGFLOW_ASSISTANT_FLOW, str)
        assert len(LANGFLOW_ASSISTANT_FLOW) > 0

    def test_translation_flow_should_be_string(self):
        """TRANSLATION_FLOW should be a non-empty string."""
        assert isinstance(TRANSLATION_FLOW, str)
        assert len(TRANSLATION_FLOW) > 0


class TestValidationRetryTemplate:
    """Tests for VALIDATION_RETRY_TEMPLATE constant."""

    def test_should_be_formattable_string(self):
        """Should be a string template with format placeholders."""
        assert isinstance(VALIDATION_RETRY_TEMPLATE, str)
        assert "{error}" in VALIDATION_RETRY_TEMPLATE
        assert "{code}" in VALIDATION_RETRY_TEMPLATE

    def test_should_format_with_error_and_code(self):
        """Should format correctly with error and code values."""
        error = "SyntaxError: invalid syntax"
        code = "def broken():"

        result = VALIDATION_RETRY_TEMPLATE.format(error=error, code=code)

        assert error in result
        assert code in result

    def test_should_include_fix_instruction(self):
        """Should include instruction to fix the error."""
        template_lower = VALIDATION_RETRY_TEMPLATE.lower()
        assert "fix" in template_lower or "correct" in template_lower

    def test_should_reference_error(self):
        """Should reference the error in the template."""
        template_lower = VALIDATION_RETRY_TEMPLATE.lower()
        assert "error" in template_lower

    def test_should_reference_code(self):
        """Should reference the code in the template."""
        template_lower = VALIDATION_RETRY_TEMPLATE.lower()
        assert "code" in template_lower

    def test_should_format_with_multiline_code(self):
        """Should format correctly with multiline code."""
        error = "IndentationError: unexpected indent"
        code = """def example():
    if True:
    print("wrong indent")"""

        result = VALIDATION_RETRY_TEMPLATE.format(error=error, code=code)

        assert error in result
        assert "def example():" in result
        assert 'print("wrong indent")' in result
