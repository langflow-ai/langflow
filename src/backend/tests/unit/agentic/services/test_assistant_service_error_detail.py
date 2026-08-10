"""Tests that the SSE error event carries the additive structured ``detail``.

Community ask: on failure, show the exact component the assistant was working
on, the concrete error, and a recommendation — instead of one truncated line.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import FlowExecutionError, IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _parse_events(events):
    return [json.loads(e.removeprefix("data: ").strip()) for e in events]


async def _stream_with_failure(original_error_message: str, *, is_superuser: bool = False):
    def streaming_factory(**_kw):
        async def always_raises():
            raise FlowExecutionError(original_error_message)
            yield  # pragma: no cover — makes this an async generator

        return always_raises()

    with (
        patch(
            f"{MODULE}.classify_intent",
            new_callable=AsyncMock,
            return_value=IntentResult(intent="question", translation="test"),
        ),
        patch(f"{MODULE}.execute_flow_file_streaming", side_effect=streaming_factory),
    ):
        gen = execute_flow_with_validation_streaming(
            flow_filename="TestFlow",
            input_value="hello",
            global_variables={},
            is_superuser=is_superuser,
        )
        return [event async for event in gen]


class TestErrorEventDetail:
    @pytest.mark.asyncio
    async def test_error_event_carries_structured_detail_with_raw_cause_for_superuser(self):
        raw = "Error building Component Agent: Error code: 401 - Incorrect API key provided"
        events = await _stream_with_failure(raw, is_superuser=True)

        errors = [p for p in _parse_events(events) if p.get("event") == "error"]
        assert len(errors) == 1

        # Backward compatibility: the friendly message is unchanged.
        assert errors[0]["message"] == "Authentication failed. Check your API key."

        detail = errors[0]["detail"]
        assert detail["component_id"] == "Agent"
        assert detail["raw_cause"] == raw
        assert detail["recommendation"] == "Check the API key in Settings → Model Providers."
        assert detail["step"] == "generating"

    @pytest.mark.asyncio
    async def test_error_detail_omits_raw_cause_for_non_superuser(self):
        # SECURITY — the raw internal error must not stream to regular users.
        raw = "Error building Component Agent: Error code: 401 - Incorrect API key sk-proj-secret"
        events = await _stream_with_failure(raw, is_superuser=False)

        errors = [p for p in _parse_events(events) if p.get("event") == "error"]
        assert len(errors) == 1
        assert errors[0]["message"] == "Authentication failed. Check your API key."

        detail = errors[0]["detail"]
        assert "raw_cause" not in detail
        assert detail["component_id"] == "Agent"
        assert detail["recommendation"] == "Check the API key in Settings → Model Providers."
        assert detail["step"] == "generating"

    @pytest.mark.asyncio
    async def test_error_detail_includes_step_and_raw_cause_for_unknown_errors_when_superuser(self):
        raw = "an utterly unclassifiable failure happened somewhere deep in the stack"
        events = await _stream_with_failure(raw, is_superuser=True)

        errors = [p for p in _parse_events(events) if p.get("event") == "error"]
        assert len(errors) == 1
        detail = errors[0]["detail"]
        assert detail["raw_cause"] == raw
        assert detail["step"] == "generating"
        assert "recommendation" not in detail
        assert "component_id" not in detail

    @pytest.mark.asyncio
    async def test_unknown_error_detail_keeps_step_but_no_raw_cause_for_non_superuser(self):
        raw = "an utterly unclassifiable failure happened somewhere deep in the stack"
        events = await _stream_with_failure(raw, is_superuser=False)

        errors = [p for p in _parse_events(events) if p.get("event") == "error"]
        assert len(errors) == 1
        detail = errors[0]["detail"]
        assert "raw_cause" not in detail
        assert detail["step"] == "generating"
