"""Tests for assistant service streaming with validation.

Tests the execute_flow_with_validation_streaming function,
including intent classification, code extraction, validation,
retry logic, and cancellation handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _make_intent(intent="question", translation="test"):
    return IntentResult(intent=intent, translation=translation)


def _make_flow_events(events):
    """Create an async generator factory from a list of (type, data) tuples."""

    async def gen():
        for event_type, event_data in events:
            yield event_type, event_data

    return gen


async def _collect_events(gen):
    """Collect all SSE events from an async generator."""
    return [event async for event in gen]


class TestIntentClassificationCall:
    """Tests that classify_intent is called correctly."""

    @pytest.mark.asyncio
    async def test_should_call_classify_intent_without_session_id(self):
        """classify_intent should NOT receive session_id parameter."""
        mock_classify = AsyncMock(return_value=_make_intent())
        flow_gen = _make_flow_events([("end", {"result": "hi"})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                session_id="session-123",
                user_id="user-1",
            )
            await _collect_events(gen)

            call_kwargs = mock_classify.call_args[1]
            assert "session_id" not in call_kwargs

    @pytest.mark.asyncio
    async def test_should_pass_provider_and_model_to_classify_intent(self):
        """classify_intent should receive provider and model_name."""
        mock_classify = AsyncMock(return_value=_make_intent())
        flow_gen = _make_flow_events([("end", {"result": "hi"})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                provider="OpenAI",
                model_name="gpt-4",
                api_key_var="OPENAI_API_KEY",
            )
            await _collect_events(gen)

            call_kwargs = mock_classify.call_args[1]
            assert call_kwargs["provider"] == "OpenAI"
            assert call_kwargs["model_name"] == "gpt-4"
            assert call_kwargs["api_key_var"] == "OPENAI_API_KEY"


class TestQAResponse:
    """Tests for Q&A (non-component) responses."""

    @pytest.mark.asyncio
    async def test_should_return_plain_text_for_qa_without_code(self):
        """Q&A response without component code should return as plain text."""
        flow_gen = _make_flow_events(
            [
                ("token", "Hello "),
                ("token", "world!"),
                ("end", {"result": "Hello world!"}),
            ]
        )

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should contain token events and a final complete event
            token_events = [e for e in events if "token" in e]
            final_complete = [e for e in events if '"event": "complete"' in e]
            assert len(token_events) >= 1
            assert len(final_complete) == 1

    @pytest.mark.asyncio
    async def test_should_return_plain_text_for_qa_with_component_code(self):
        """Q&A response containing component code should NOT trigger validation.

        When intent is "question", code extraction is skipped entirely to prevent
        example code in explanatory answers from being treated as component generation.
        """
        component_code = (
            "from langflow.custom import Component\n\n"
            "class MyComponent(Component):\n"
            "    description = 'test'\n"
            "    inputs = []\n"
        )

        response_text = f"Here's an example:\n\n```python\n{component_code}\n```\n\nHope that helps!"
        flow_gen = _make_flow_events([("end", {"result": response_text})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how do I create a component?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should NOT contain validation events — Q&A skips code extraction
            validation_events = [e for e in events if "extracting_code" in e or '"validating"' in e]
            assert len(validation_events) == 0

            # Should contain a complete event with the full text response
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert len(complete_events) == 1

    @pytest.mark.asyncio
    async def test_should_return_plain_text_when_question_response_contains_example_code(self):
        """Q&A response with example component code should NOT trigger validation.

        Bug: User asks "how do I create a custom component?" and the LLM responds
        with an explanation plus an example code snippet. The fallback code extraction
        detects 'class SumComponent(Component)' in the example and triggers the
        validation pipeline, showing a component card instead of the text answer.
        """
        # Use a raw string with triple-backtick code block (real markdown)
        explanation_with_example = (
            "To create a custom component, you need to:\n\n"
            "1. Create a Python file\n"
            "2. Define a class\n\n"
            "```python\n"
            "from lfx.custom import Component\n"
            "from lfx.io import Output\n"
            "from lfx.schema import Data\n\n"
            "class SumComponent(Component):\n"
            "    display_name = 'Sum'\n"
            "    description = 'Adds two numbers'\n"
            "    inputs = []\n"
            "    outputs = [Output(name='result', display_name='Result', method='run')]\n\n"
            "    def run(self) -> Data:\n"
            "        return Data(data={'result': 42})\n"
            "```\n"
        )
        flow_gen = _make_flow_events([("end", {"result": explanation_with_example})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how do I create a custom component?",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should NOT contain validation-related events (extracting_code, validating, validated)
            validation_events = [e for e in events if "extracting_code" in e or "validating" in e]
            assert len(validation_events) == 0, (
                f"Q&A response with example code should not trigger validation. "
                f"Got validation events: {validation_events}"
            )

            # Should contain a complete event with the full text (not component card)
            complete_events = [e for e in events if '"event": "complete"' in e]
            assert len(complete_events) == 1


class TestComponentGeneration:
    """Tests for component generation flow."""

    @pytest.mark.asyncio
    async def test_should_emit_progress_events_on_successful_validation(self):
        """Should emit generating_component and validation progress events."""
        component_code = "class MyComp(Component): pass"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "MyComp"

        response_text = f"```python\n{component_code}\n```"
        flow_gen = _make_flow_events([("end", {"result": response_text})])

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.validate_component_runtime", return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            events = await _collect_events(gen)

            # Should have progress events for generation and validation steps
            progress_steps = [
                e
                for e in events
                if any(step in e for step in ["generating_component", "extracting_code", "validating", "validated"])
            ]
            assert len(progress_steps) >= 2

    @pytest.mark.asyncio
    async def test_should_retry_on_validation_failure(self):
        """Should retry with error context when validation fails."""
        component_code = "class BadComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Missing inputs"
        mock_fail.class_name = "BadComp"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "FixedComp"

        call_count = 0

        async def mock_streaming():
            nonlocal call_count
            call_count += 1
            yield "end", {"result": f"```python\n{component_code}\n```"}

        response_text = f"```python\n{component_code}\n```"

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", side_effect=[mock_fail, mock_success]),
            patch(f"{MODULE}.validate_component_runtime", return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            events = await _collect_events(gen)

            # Should have called flow twice (first attempt + one retry)
            assert call_count == 2

            # Should have retry-related events
            retry_events = [e for e in events if "retry" in e.lower() or "validation_failed" in e.lower()]
            assert len(retry_events) >= 1

    @pytest.mark.asyncio
    async def test_should_return_error_when_max_retries_exhausted(self):
        """Should return validation error when all retries fail."""
        component_code = "class BrokenComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Persistent error"
        mock_fail.class_name = "BrokenComp"

        async def mock_streaming():
            yield "end", {"result": f"```python\n{component_code}\n```"}

        response_text = f"```python\n{component_code}\n```"

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("generate_component")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_fail),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=1,
            )
            events = await _collect_events(gen)

            # Final event should contain validated=False info
            complete_events = [e for e in events if "complete" in e.lower()]
            assert len(complete_events) >= 1


class TestCancellation:
    """Tests for client disconnect / cancellation handling."""

    @pytest.mark.asyncio
    async def test_should_emit_cancelled_event_on_disconnect(self):
        """Should emit cancelled event when client disconnects."""

        async def is_disconnected():
            return True

        with patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
                is_disconnected=is_disconnected,
            )
            events = await _collect_events(gen)

            cancelled_events = [e for e in events if "cancelled" in e.lower()]
            assert len(cancelled_events) >= 1


class TestErrorHandling:
    """Tests for error handling in flow execution."""

    @pytest.mark.asyncio
    async def test_should_emit_error_event_on_http_exception(self):
        """Should emit error event when flow execution raises HTTPException."""
        from fastapi import HTTPException

        async def mock_streaming():
            raise HTTPException(status_code=500, detail="Internal server error")
            yield  # makes this an async generator

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
            )
            events = await _collect_events(gen)

            error_events = [e for e in events if "error" in e.lower()]
            assert len(error_events) >= 1

    @pytest.mark.asyncio
    async def test_should_emit_error_when_no_result(self):
        """Should emit error event when flow returns no result."""
        flow_gen = _make_flow_events([])  # No events = no result

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
            )
            events = await _collect_events(gen)

            error_events = [e for e in events if "error" in e.lower() or "no result" in e.lower()]
            assert len(error_events) >= 1
