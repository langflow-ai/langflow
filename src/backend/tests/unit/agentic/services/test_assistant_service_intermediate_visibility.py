"""Tests for intermediate visibility in assistant service streaming.

Verifies that progress events include component_code, error, and class_name
at the right steps, so the frontend can show live previews during generation.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _make_intent(intent="generate_component", translation="test"):
    return IntentResult(intent=intent, translation=translation)


def _safe_security():
    """Return a mock SecurityScanResult that passes."""
    result = MagicMock()
    result.is_safe = True
    result.violations = ()
    return result


def _parse_sse_events(raw_events: list[str]) -> list[dict]:
    """Parse raw SSE strings into dicts."""
    parsed = []
    for raw in raw_events:
        if raw.startswith("data: "):
            data_str = raw[len("data: ") :].strip()
            parsed.append(json.loads(data_str))
    return parsed


def _filter_events_by_step(events: list[dict], step: str) -> list[dict]:
    """Filter parsed events by progress step."""
    return [e for e in events if e.get("event") == "progress" and e.get("step") == step]


async def _collect_raw_events(gen) -> list[str]:
    """Collect all raw SSE strings from an async generator."""
    return [event async for event in gen]


class TestValidatingStepIncludesCode:
    """The 'validating' progress event must include component_code.

    So the frontend can show a live preview before validation completes.
    """

    @pytest.mark.asyncio
    async def test_should_include_component_code_in_validating_event(self):
        component_code = "from langflow.custom import Component\n\nclass MyComp(Component):\n    inputs = []\n"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "MyComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            validating_events = _filter_events_by_step(events, "validating")
            assert len(validating_events) == 1

            validating = validating_events[0]
            assert validating["component_code"] == component_code

    @pytest.mark.asyncio
    async def test_should_include_component_code_before_validation_result(self):
        """The validating event should arrive BEFORE the validated event.

        Giving the frontend time to show the code preview.
        """
        component_code = "class PreviewComp(Component):\n    pass"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "PreviewComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            progress_steps = [e["step"] for e in events if e.get("event") == "progress"]
            validating_idx = progress_steps.index("validating")
            validated_idx = progress_steps.index("validated")
            assert validating_idx < validated_idx


class TestValidationFailedIncludesDetails:
    """The 'validation_failed' progress event must include error details.

    Includes class_name and component_code for debugging in the UI.
    """

    @pytest.mark.asyncio
    async def test_should_include_error_and_code_in_validation_failed(self):
        component_code = "class BadComp(Component):\n    pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "AttributeError: missing 'inputs'"
        mock_fail.class_name = "BadComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_fail),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=0,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            failed_events = _filter_events_by_step(events, "validation_failed")
            assert len(failed_events) == 1

            failed = failed_events[0]
            assert failed["error"] == "AttributeError: missing 'inputs'"
            assert failed["class_name"] == "BadComp"
            assert failed["component_code"] == component_code

    @pytest.mark.asyncio
    async def test_should_include_message_in_validation_failed(self):
        component_code = "class MsgComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "SyntaxError"
        mock_fail.class_name = "MsgComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_fail),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=1,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            failed = _filter_events_by_step(events, "validation_failed")[0]
            assert failed["message"] == "Validation failed"


class TestRetryingStepIncludesError:
    """The 'retrying' progress event must include the error that caused the retry.

    So the UI can show why it's retrying.
    """

    @pytest.mark.asyncio
    async def test_should_include_error_in_retrying_event(self):
        component_code = "class RetryComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "ImportError: cannot import 'foo'"
        mock_fail.class_name = "RetryComp"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "RetryComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", side_effect=[mock_fail, mock_success]),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            retrying_events = _filter_events_by_step(events, "retrying")
            assert len(retrying_events) == 1

            retrying = retrying_events[0]
            assert retrying["error"] == "ImportError: cannot import 'foo'"

    @pytest.mark.asyncio
    async def test_should_include_retry_attempt_info_in_retrying_event(self):
        component_code = "class AttemptComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Error"
        mock_fail.class_name = "AttemptComp"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "AttemptComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", side_effect=[mock_fail, mock_success]),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            retrying = _filter_events_by_step(events, "retrying")[0]
            assert retrying["attempt"] == 1  # First attempt (1-indexed)
            assert retrying["max_attempts"] == 3  # max_retries=2 means 3 total attempts


class TestProgressEventSequence:
    """Tests for the correct ordering and completeness of progress events.

    Covers the component generation pipeline.
    """

    @pytest.mark.asyncio
    async def test_should_emit_full_success_sequence(self):
        """Successful generation should emit the full event sequence.

        generating_component → generation_complete → extracting_code → validating → validated → complete
        """
        component_code = "class SeqComp(Component):\n    pass"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "SeqComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            progress_steps = [e["step"] for e in events if e.get("event") == "progress"]
            expected_steps = [
                "generating_component",
                "generation_complete",
                "extracting_code",
                "validating",
                "validated",
            ]
            assert progress_steps == expected_steps

    @pytest.mark.asyncio
    async def test_should_emit_retry_sequence_on_failure(self):
        """Failed validation with retry should emit the retry sequence.

        generating_component → generation_complete → extracting_code → validating →
        validation_failed → retrying → generating_component → ...
        """
        component_code = "class RetrySeq(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Error"
        mock_fail.class_name = "RetrySeq"

        mock_success = MagicMock()
        mock_success.is_valid = True
        mock_success.class_name = "RetrySeq"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", side_effect=[mock_fail, mock_success]),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=2,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            progress_steps = [e["step"] for e in events if e.get("event") == "progress"]
            # First attempt fails, then retry succeeds
            expected_steps = [
                "generating_component",
                "generation_complete",
                "extracting_code",
                "validating",
                "validation_failed",
                "retrying",
                # Second attempt
                "generating_component",
                "generation_complete",
                "extracting_code",
                "validating",
                "validated",
            ]
            assert progress_steps == expected_steps

    @pytest.mark.asyncio
    async def test_should_end_with_complete_event_on_success(self):
        component_code = "class CompleteComp(Component): pass"
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.class_name = "CompleteComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_validation),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.validate_component_runtime", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            complete_events = [e for e in events if e.get("event") == "complete"]
            assert len(complete_events) == 1

            complete = complete_events[0]
            assert complete["data"]["validated"] is True
            assert complete["data"]["class_name"] == "CompleteComp"
            assert complete["data"]["component_code"] == component_code

    @pytest.mark.asyncio
    async def test_should_end_with_complete_event_on_max_retries(self):
        component_code = "class ExhaustedComp(Component): pass"
        mock_fail = MagicMock()
        mock_fail.is_valid = False
        mock_fail.error = "Persistent error"
        mock_fail.class_name = "ExhaustedComp"

        response_text = f"```python\n{component_code}\n```"

        async def mock_streaming(**_kw):
            yield "end", {"result": response_text}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent()),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
            patch(f"{MODULE}.extract_component_code", return_value=component_code),
            patch(f"{MODULE}.validate_component_code", return_value=mock_fail),
            patch(f"{MODULE}.scan_code_security", return_value=_safe_security()),
            patch(f"{MODULE}.extract_response_text", return_value=response_text),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="create a component",
                global_variables={},
                max_retries=1,
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            complete_events = [e for e in events if e.get("event") == "complete"]
            assert len(complete_events) == 1

            complete = complete_events[0]
            assert complete["data"]["validated"] is False
            assert complete["data"]["validation_error"] == "Persistent error"
            assert complete["data"]["component_code"] == component_code


class TestQADoesNotIncludeCode:
    """Q&A responses should not include component_code in progress events."""

    @pytest.mark.asyncio
    async def test_should_not_include_component_code_in_qa_progress(self):
        async def mock_streaming(**_kw):
            yield "token", "Hello "
            yield "token", "world!"
            yield "end", {"result": "Hello world!"}

        with (
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent("question")),
            patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: mock_streaming()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="what is langflow?",
                global_variables={},
            )
            raw_events = await _collect_raw_events(gen)
            events = _parse_sse_events(raw_events)

            progress_events = [e for e in events if e.get("event") == "progress"]
            for event in progress_events:
                assert "component_code" not in event
