"""Tests for streaming validation flow in the agentic module.

These tests validate the retry logic and SSE event emission for component generation.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.helpers.code_extraction import extract_python_code
from langflow.agentic.helpers.sse import (
    format_complete_event,
    format_error_event,
    format_progress_event,
)
from langflow.agentic.helpers.validation import validate_component_code
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation,
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import (
    VALIDATION_RETRY_TEMPLATE,
    IntentResult,
)

# Sample valid Langflow component code
VALID_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class HelloWorldComponent(Component):
    display_name = "Hello World"
    description = "A simple hello world component."

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self) -> Message:
        return Message(text=f"Hello, {self.input_value}!")
"""

# Invalid component code (syntax error but has inputs/outputs to pass extraction)
INVALID_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output

class BrokenComponent(Component)  # Missing colon here
    display_name = "Broken"

    inputs = [
        MessageTextInput(name="text", display_name="Text"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]
"""

# Incomplete code that got cut off (simulating rate limit/token limit)
CUTOFF_COMPONENT_CODE = """from __future__ import annotations

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class SentimentAnalyzer(Component):
    display_name = "Sentiment Analyzer"
    description = "Analyzes sentiment of text"

    inputs = [
        MessageTextInput(name="text", display_name="Text"),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="analyze"),
    ]

    def analyze(self) -> Message:
        # This code is cut off mid-implementation"""


class TestSSEEventFormatting:
    """Tests for SSE event formatting functions."""

    def testformat_progress_event_format(self):
        """Should format progress event correctly."""
        result = format_progress_event("generating", 1, 4)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        # Parse the JSON
        json_str = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_str)

        assert data["event"] == "progress"
        assert data["step"] == "generating"
        assert data["attempt"] == 1
        assert data["max_attempts"] == 4

    def testformat_progress_event_validating_step(self):
        """Should format validating progress event correctly."""
        result = format_progress_event("validating", 2, 4)

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["step"] == "validating"
        assert data["attempt"] == 2

    def testformat_complete_event_format(self):
        """Should format complete event correctly."""
        test_data = {"result": "test", "validated": True, "class_name": "TestComponent"}
        result = format_complete_event(test_data)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["event"] == "complete"
        assert data["data"]["validated"] is True
        assert data["data"]["class_name"] == "TestComponent"

    def testformat_error_event_format(self):
        """Should format error event correctly."""
        result = format_error_event("Rate limit exceeded")

        json_str = result[6:-2]
        data = json.loads(json_str)

        assert data["event"] == "error"
        assert data["message"] == "Rate limit exceeded"


class TestValidationRetryTemplate:
    """Tests for the validation retry prompt template."""

    def test_retry_template_contains_error(self):
        """Should include error message in retry template."""
        error = "SyntaxError: invalid syntax"
        code = "def broken():"

        result = VALIDATION_RETRY_TEMPLATE.format(error=error, code=code)

        assert error in result
        assert code in result
        assert "fix" in result.lower() or "correct" in result.lower()


def _mock_streaming_result(result):
    """Create an async generator that yields a single end event with the given result."""

    async def _gen(*_args, **_kwargs):
        yield ("end", result)

    return _gen


def _mock_streaming_sequence(results):
    """Create an async generator factory that yields different results on each call."""
    call_count = 0

    async def _gen(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        yield ("end", results[min(call_count - 1, len(results) - 1)])

    return _gen


def _mock_intent_classification(intent: str = "generate_component"):
    """Create an async mock that returns IntentResult."""

    async def _mock(*_args, **_kwargs):
        return IntentResult(translation="mocked", intent=intent)

    return _mock


class TestStreamingValidationFlow:
    """Tests for execute_flow_with_validation_streaming function."""

    @pytest.mark.asyncio
    async def test_valid_code_first_try_returns_validated(self):
        """When code is valid on first try, should return validated=True."""
        mock_flow_result = {"result": f"Here is your component:\n\n```python\n{VALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(mock_flow_result),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a hello world component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        # Should have progress events + complete event
        assert len(events) >= 2

        # Parse all events
        parsed_events = []
        for event in events:
            json_str = event[6:-2]  # Remove "data: " and "\n\n"
            parsed_events.append(json.loads(json_str))

        # Should have generating_component progress (component generation mode)
        generating_events = [
            e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "generating_component"
        ]
        assert len(generating_events) == 1

        # Should have validating progress
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 1

        # Should have complete event with validated=True
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["data"]["validated"] is True
        assert complete_events[0]["data"]["class_name"] == "HelloWorldComponent"

    @pytest.mark.asyncio
    async def test_invalid_code_retries_until_success(self):
        """When code is invalid, should retry with error context until valid."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_response = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_sequence([invalid_response, valid_response]),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        # Parse events
        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have 2 generating_component events (attempt 1 and 2)
        generating_events = [
            e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "generating_component"
        ]
        assert len(generating_events) == 2

        # Should have 2 validating events
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 2

        # Should have complete event with validated=True (after retry)
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["data"]["validated"] is True
        assert complete_events[0]["data"]["validation_attempts"] == 1

    @pytest.mark.asyncio
    async def test_all_retries_fail_returns_validation_error(self):
        """When all retries fail, should return validated=False with error."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(invalid_response),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=2,  # Will try 3 times total (1 + 2 retries)
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have 3 generating_component events (max_retries + 1)
        generating_events = [
            e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "generating_component"
        ]
        assert len(generating_events) == 3

        # Should have complete event with validated=False
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["data"]["validated"] is False
        assert complete_events[0]["data"]["validation_error"] is not None
        assert complete_events[0]["data"]["validation_attempts"] == 2

    @pytest.mark.asyncio
    async def test_no_code_in_response_returns_as_is(self):
        """When response has no code (question intent), should return without validation."""
        text_only_response = {"result": "Langflow is a visual flow builder for LLM applications."}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("question"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(text_only_response),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="what is langflow?",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # For question intent, should have generating event (not generating_component)
        generating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "generating"]
        assert len(generating_events) == 1

        # Should NOT have validating event
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 0

        # Complete event should NOT have validated field
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert "validated" not in complete_events[0]["data"]

    @pytest.mark.asyncio
    async def test_flow_execution_error_returnsformat_error_event(self):
        """When flow execution fails, should return SSE error event."""
        from fastapi import HTTPException

        async def mock_streaming_error(*_args, **_kwargs):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
            yield  # makes this an async generator

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=mock_streaming_error,
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have error event
        error_events = [e for e in parsed_events if e.get("event") == "error"]
        assert len(error_events) == 1
        assert "rate limit" in error_events[0]["message"].lower()


class TestValidationRetryBehavior:
    """Tests specifically for the retry behavior with error context."""

    @pytest.mark.asyncio
    async def test_retry_includes_previous_error_in_prompt(self):
        """When retrying, should include the validation error in the new prompt."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_response = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        captured_inputs = []
        call_count = 0

        async def mock_streaming(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            captured_inputs.append(_kwargs.get("input_value"))
            if call_count == 1:
                yield ("end", invalid_response)
            else:
                yield ("end", valid_response)

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=mock_streaming,
            ),
        ):
            # Consume the generator to trigger the mock calls
            _ = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        # Should have captured 2 inputs
        assert len(captured_inputs) == 2

        # First input is the original user input (translation is used only for intent classification)
        assert captured_inputs[0] == "create a component"

        # Second input should contain error context
        assert "error" in captured_inputs[1].lower()
        assert "fix" in captured_inputs[1].lower() or "correct" in captured_inputs[1].lower()
        # Should include the broken code
        assert INVALID_COMPONENT_CODE.strip() in captured_inputs[1] or "BrokenComponent" in captured_inputs[1]


class TestNonStreamingValidation:
    """Tests for the non-streaming validation function."""

    @pytest.mark.asyncio
    async def test_non_streaming_valid_code_returns_validated(self):
        """Non-streaming validation should work the same as streaming."""
        mock_flow_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_flow_result,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a hello world component",
                global_variables={},
                max_retries=3,
            )

        assert result["validated"] is True
        assert result["class_name"] == "HelloWorldComponent"
        assert result["validation_attempts"] == 1

    @pytest.mark.asyncio
    async def test_non_streaming_retries_on_failure(self):
        """Non-streaming should retry until valid code is generated."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_response = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_execute_flow(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return invalid_response
            return valid_response

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute_flow,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=3,
            )

        assert result["validated"] is True
        assert result["validation_attempts"] == 2

    @pytest.mark.asyncio
    async def test_non_streaming_max_retries_returns_error(self):
        """After max retries, should return validation error."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=invalid_response,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )

        assert result["validated"] is False
        assert result["validation_error"] is not None


class TestResponseWithTextAndCode:
    """Tests for handling responses that contain both text and code.

    This is the main issue being debugged - LLM responses that include
    explanatory text along with code blocks.
    """

    @pytest.mark.asyncio
    async def test_extracts_code_from_response_with_text_before(self):
        """Should correctly extract and validate code when text comes before it."""
        response_with_text = {
            "result": f"""I apologize for the rate limit issue. Let me help you create the component.

Here's the implementation:

```python
{VALID_COMPONENT_CODE}
```

This component will process your input."""
        }

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(response_with_text),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have validating event
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 1

        # Should have complete event with validated=True
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["data"]["validated"] is True

    @pytest.mark.asyncio
    async def test_extracts_code_from_unclosed_block_with_text(self):
        """Should correctly extract code from unclosed block with text before it."""
        response_with_unclosed = {
            "result": f"""I apologize for the rate limit issue.

```python
{VALID_COMPONENT_CODE}"""
        }

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(response_with_unclosed),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should validate and pass
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["data"]["validated"] is True

    @pytest.mark.asyncio
    async def test_complete_event_includes_component_code(self):
        """Complete event should include the extracted component_code field."""
        mock_flow_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(mock_flow_result),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1

        complete_data = complete_events[0]["data"]
        assert "component_code" in complete_data
        assert "HelloWorldComponent" in complete_data["component_code"]

    @pytest.mark.asyncio
    async def test_validation_failure_includes_component_code(self):
        """When validation fails, should still include the attempted code."""
        invalid_response = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(invalid_response),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=0,  # No retries - fail immediately
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1

        complete_data = complete_events[0]["data"]
        assert complete_data["validated"] is False
        assert "component_code" in complete_data
        assert "BrokenComponent" in complete_data["component_code"]


class TestRealWorldScenarios:
    """Tests for real-world scenarios the user encountered.

    These tests simulate the exact patterns seen in production.
    """

    @pytest.mark.asyncio
    async def test_response_with_apology_and_cutoff_code(self):
        """Should handle response with apology text and cut-off/incomplete code."""
        # This simulates the exact response the user showed
        response_with_apology = {
            "result": f"""I apologize for the rate limit issue. Let me create the component.

Here's the implementation:

```python
{CUTOFF_COMPONENT_CODE}"""
        }

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(response_with_apology),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a sentiment analyzer",
                    global_variables={},
                    max_retries=0,  # Test with no retries to see immediate behavior
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have validating event (code was extracted)
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 1, "Code should be extracted and validation attempted"

        # Should have complete event
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete_events) == 1

        complete_data = complete_events[0]["data"]

        # Validation should FAIL because code is incomplete
        assert complete_data["validated"] is False, "Incomplete code should fail validation"

        # Should have validation error
        assert complete_data.get("validation_error") is not None, "Should have validation error"

        # Should include the extracted code
        assert "component_code" in complete_data, "Should include extracted code"
        assert "SentimentAnalyzer" in complete_data["component_code"]

    @pytest.mark.asyncio
    async def test_response_with_apology_and_cutoff_code_with_retries(self):
        """After exhausting retries with cutoff code, should return validated=False."""
        cutoff_response = {
            "result": f"""I apologize for the issue.

```python
{CUTOFF_COMPONENT_CODE}"""
        }

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_result(cutoff_response),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=2,  # Will try 3 times
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        # Should have 3 generating_component events
        generating_events = [
            e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "generating_component"
        ]
        assert len(generating_events) == 3

        # Should have 3 validating events
        validating_events = [e for e in parsed_events if e.get("event") == "progress" and e.get("step") == "validating"]
        assert len(validating_events) == 3

        # Complete event should have validated=False
        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        complete_data = complete_events[0]["data"]

        assert complete_data["validated"] is False
        assert complete_data["validation_attempts"] == 2

    @pytest.mark.asyncio
    async def test_cutoff_code_retry_gets_valid_code(self):
        """If retry gets valid code, should return validated=True."""
        cutoff_response = {
            "result": f"""Error occurred.

```python
{CUTOFF_COMPONENT_CODE}"""
        }
        valid_response = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        with (
            patch(
                "langflow.agentic.services.assistant_service.classify_intent",
                side_effect=_mock_intent_classification("generate_component"),
            ),
            patch(
                "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
                side_effect=_mock_streaming_sequence([cutoff_response, cutoff_response, valid_response]),
            ),
        ):
            events = [
                event
                async for event in execute_flow_with_validation_streaming(
                    flow_filename="test.json",
                    input_value="create a component",
                    global_variables={},
                    max_retries=3,
                )
            ]

        parsed_events = [json.loads(e[6:-2]) for e in events]

        complete_events = [e for e in parsed_events if e.get("event") == "complete"]
        complete_data = complete_events[0]["data"]

        # Should eventually succeed
        assert complete_data["validated"] is True
        assert complete_data["validation_attempts"] == 2
        assert complete_data["class_name"] == "HelloWorldComponent"

    def test_code_extraction_from_exact_user_response(self):
        """Test extraction from the exact response pattern user showed."""
        # Exact pattern from user's screenshot
        user_response = """I apologize for the rate limit issue. Let me create the component.

Here's the implementation:

```python
from __future__ import annotations

from langflow.custom import Component
from langflow.io import MessageTextInput, Output


class SentimentComponent(Component):
    display_name = "Sentiment"

    inputs = [
        MessageTextInput(name="text", display_name="Input"),
    ]

    outputs = [
        Output(name="output", method="run"),
    ]

    def run(self):"""

        # Should extract the code
        code = extract_python_code(user_response)
        assert code is not None, "Should extract code from user response"
        assert "SentimentComponent" in code
        assert "from __future__" in code

        # Validate should fail due to incomplete code
        validation = validate_component_code(code)
        assert validation.is_valid is False, "Incomplete code should fail validation"
        assert validation.error is not None
