"""Tests for assistant service with validation and retry logic."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    LANGFLOW_ASSISTANT_FLOW,
    MAX_VALIDATION_RETRIES,
    VALIDATION_RETRY_TEMPLATE,
    VALIDATION_UI_DELAY_SECONDS,
    execute_flow_with_validation,
    execute_flow_with_validation_streaming,
)

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

INVALID_COMPONENT_CODE = """from langflow.custom import Component

class BrokenComponent(Component)
    display_name = "Broken"
"""

INCOMPLETE_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output


class IncompleteComponent(Component):
    display_name = "Incomplete"

    inputs = [
        MessageTextInput(name="text", display_name="Text"),
    ]

    def analyze(self):
        # This code is cut off mid-implementation"""


class TestConstants:
    """Tests for module constants."""

    def test_should_have_max_validation_retries(self):
        assert isinstance(MAX_VALIDATION_RETRIES, int)
        assert MAX_VALIDATION_RETRIES > 0

    def test_should_have_validation_ui_delay(self):
        assert isinstance(VALIDATION_UI_DELAY_SECONDS, float)
        assert VALIDATION_UI_DELAY_SECONDS >= 0

    def test_should_have_langflow_assistant_flow(self):
        assert isinstance(LANGFLOW_ASSISTANT_FLOW, str)
        assert LANGFLOW_ASSISTANT_FLOW.endswith(".json")

    def test_validation_retry_template_should_have_placeholders(self):
        assert "{error}" in VALIDATION_RETRY_TEMPLATE
        assert "{code}" in VALIDATION_RETRY_TEMPLATE


class TestValidationRetryTemplate:
    """Tests for VALIDATION_RETRY_TEMPLATE."""

    def test_should_format_with_error_and_code(self):
        error = "SyntaxError: invalid syntax"
        code = "def broken():"

        result = VALIDATION_RETRY_TEMPLATE.format(error=error, code=code)

        assert error in result
        assert code in result

    def test_should_include_instruction_to_fix(self):
        result = VALIDATION_RETRY_TEMPLATE.format(error="error", code="code")

        assert "fix" in result.lower() or "correct" in result.lower()


class TestExecuteFlowWithValidation:
    """Tests for execute_flow_with_validation function."""

    @pytest.mark.asyncio
    async def test_should_return_validated_true_for_valid_code(self):
        mock_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=mock_result,
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
        assert "component_code" in result

    @pytest.mark.asyncio
    async def test_should_retry_on_invalid_code(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_execute(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return invalid_result
            return valid_result

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute,
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
    async def test_should_return_validation_error_after_max_retries(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=invalid_result,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )

        assert result["validated"] is False
        assert "validation_error" in result
        assert result["validation_attempts"] == 3  # 1 + 2 retries

    @pytest.mark.asyncio
    async def test_should_return_as_is_when_no_code_in_response(self):
        text_result = {"result": "Langflow is a visual flow builder."}

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=text_result,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="what is langflow?",
                global_variables={},
                max_retries=3,
            )

        assert "validated" not in result
        assert result["result"] == "Langflow is a visual flow builder."

    @pytest.mark.asyncio
    async def test_should_pass_error_context_on_retry(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        captured_inputs = []

        async def mock_execute(**kwargs):
            captured_inputs.append(kwargs.get("input_value"))
            if len(captured_inputs) == 1:
                return invalid_result
            return valid_result

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute,
        ):
            await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=3,
            )

        assert len(captured_inputs) == 2
        assert captured_inputs[0] == "create a component"
        assert "error" in captured_inputs[1].lower()
        assert "BrokenComponent" in captured_inputs[1]


class TestExecuteFlowWithValidationStreaming:
    """Tests for execute_flow_with_validation_streaming function."""

    @pytest.mark.asyncio
    async def test_should_emit_progress_events_for_valid_code(self):
        mock_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        async def mock_streaming(*_args, **_kwargs):
            yield ("token", "Hello")
            yield ("end", mock_result)

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        # Should have generating progress
        generating = [e for e in parsed_events if e.get("step") == "generating"]
        assert len(generating) == 1

        # Should have generation_complete
        complete_gen = [e for e in parsed_events if e.get("step") == "generation_complete"]
        assert len(complete_gen) == 1

        # Should have extracting_code
        extracting = [e for e in parsed_events if e.get("step") == "extracting_code"]
        assert len(extracting) == 1

        # Should have validating
        validating = [e for e in parsed_events if e.get("step") == "validating"]
        assert len(validating) == 1

        # Should have validated
        validated = [e for e in parsed_events if e.get("step") == "validated"]
        assert len(validated) == 1

        # Should have complete event
        complete = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete) == 1
        assert complete[0]["data"]["validated"] is True

    @pytest.mark.asyncio
    async def test_should_emit_token_events(self):
        mock_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        async def mock_streaming(*_args, **_kwargs):
            yield ("token", "Hello")
            yield ("token", " World")
            yield ("end", mock_result)

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        token_events = [e for e in parsed_events if e.get("event") == "token"]
        assert len(token_events) == 2
        assert token_events[0]["chunk"] == "Hello"
        assert token_events[1]["chunk"] == " World"

    @pytest.mark.asyncio
    async def test_should_emit_validation_failed_and_retrying_events(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}
        valid_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_streaming(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            yield ("token", "code")
            if call_count == 1:
                yield ("end", invalid_result)
            else:
                yield ("end", valid_result)

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        # Should have validation_failed
        validation_failed = [e for e in parsed_events if e.get("step") == "validation_failed"]
        assert len(validation_failed) == 1

        # Should have retrying
        retrying = [e for e in parsed_events if e.get("step") == "retrying"]
        assert len(retrying) == 1

        # Should ultimately succeed
        complete = [e for e in parsed_events if e.get("event") == "complete"]
        assert complete[0]["data"]["validated"] is True

    @pytest.mark.asyncio
    async def test_should_emit_error_event_on_http_exception(self):
        from fastapi import HTTPException

        async def mock_streaming(*_args, **_kwargs):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
            yield  # Make it a generator

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        error_events = [e for e in parsed_events if e.get("event") == "error"]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_should_not_emit_validation_events_for_text_response(self):
        text_result = {"result": "Langflow is a visual flow builder."}

        async def mock_streaming(*_args, **_kwargs):
            yield ("token", "Langflow")
            yield ("end", text_result)

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        # Should NOT have validating event
        validating = [e for e in parsed_events if e.get("step") == "validating"]
        assert len(validating) == 0

        # Should have complete without validated field
        complete = [e for e in parsed_events if e.get("event") == "complete"]
        assert len(complete) == 1
        assert "validated" not in complete[0]["data"]

    @pytest.mark.asyncio
    async def test_should_include_component_code_in_complete_event(self):
        mock_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        async def mock_streaming(*_args, **_kwargs):
            yield ("end", mock_result)

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file_streaming",
            side_effect=mock_streaming,
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

        complete = [e for e in parsed_events if e.get("event") == "complete"]
        assert "component_code" in complete[0]["data"]
        assert "HelloWorldComponent" in complete[0]["data"]["component_code"]


class TestRetryBehavior:
    """Tests specifically for retry behavior."""

    @pytest.mark.asyncio
    async def test_should_respect_max_retries_parameter(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_execute(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return invalid_result

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute,
        ):
            await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=5,
            )

        assert call_count == 6  # 1 initial + 5 retries

    @pytest.mark.asyncio
    async def test_should_work_with_zero_retries(self):
        invalid_result = {"result": f"```python\n{INVALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_execute(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return invalid_result

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=0,
            )

        assert call_count == 1
        assert result["validated"] is False


class TestRealWorldScenarios:
    """Tests for real-world scenarios."""

    @pytest.mark.asyncio
    async def test_should_handle_response_with_apology_and_code(self):
        response_with_apology = {
            "result": f"""I apologize for the rate limit issue.

Here's the implementation:

```python
{VALID_COMPONENT_CODE}
```

Let me know if you need changes."""
        }

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            new_callable=AsyncMock,
            return_value=response_with_apology,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=3,
            )

        assert result["validated"] is True
        assert result["class_name"] == "HelloWorldComponent"

    @pytest.mark.asyncio
    async def test_should_handle_incomplete_code_with_retry(self):
        incomplete_result = {"result": f"```python\n{INCOMPLETE_COMPONENT_CODE}"}
        valid_result = {"result": f"```python\n{VALID_COMPONENT_CODE}\n```"}

        call_count = 0

        async def mock_execute(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return incomplete_result
            return valid_result

        with patch(
            "langflow.agentic.services.assistant_service.execute_flow_file",
            side_effect=mock_execute,
        ):
            result = await execute_flow_with_validation(
                flow_filename="test.json",
                input_value="create a component",
                global_variables={},
                max_retries=3,
            )

        assert result["validated"] is True
        assert result["validation_attempts"] == 3
