"""Tests that per-turn LLM cost surfaces in the SSE complete event.

The assistant calls (at least) two LLMs per turn — the TranslationFlow for
intent classification and the FlowBuilderAssistant for the agent's work.
The user only sees one ``complete`` SSE event at the end of the turn, so the
service is responsible for accumulating the cost of every LLM call into
``data.usage`` and reporting the wall-time as ``data.duration_seconds``.

The frontend already has a renderer for this data shape (``MessageMetadata``
in the playground); these tests pin the SSE contract that feeds it.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.agentic.services.assistant_service import execute_flow_with_validation_streaming
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"


def _make_intent(
    *,
    intent: str = "question",
    translation: str = "test",
    tokens: dict | None = None,
) -> IntentResult:
    return IntentResult(intent=intent, translation=translation, tokens=tokens)


def _make_flow_events(events):
    async def gen():
        for event_type, event_data in events:
            yield event_type, event_data

    return gen


async def _collect_events(gen):
    return [event async for event in gen]


def _parse_complete_data(event_str: str) -> dict:
    """Strip the SSE prefix and parse a single complete event's ``data`` dict."""
    payload_str = event_str.removeprefix("data: ").rstrip()
    payload = json.loads(payload_str)
    assert payload["event"] == "complete"
    return payload["data"]


class TestAssistantPerTurnUsageReporting:
    """Per-turn usage and duration must surface in the SSE complete event.

    The ``complete`` payload carries ``usage`` (input/output/total tokens) and
    ``duration_seconds`` for every turn so the chat can render the same cost
    badge already used by the playground.
    """

    @pytest.mark.asyncio
    async def test_should_sum_intent_and_agent_tokens_in_complete_event(self):
        intent_tokens = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}
        agent_tokens = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

        mock_classify = AsyncMock(return_value=_make_intent(tokens=intent_tokens))
        flow_gen = _make_flow_events([("end", {"result": "hi", "_metrics": agent_tokens})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hello",
                global_variables={},
            )
            events = await _collect_events(gen)

        completes = [e for e in events if '"event": "complete"' in e]
        assert len(completes) == 1, events
        data = _parse_complete_data(completes[0])
        assert data["usage"] == {"input_tokens": 110, "output_tokens": 54, "total_tokens": 164}
        assert isinstance(data["duration_seconds"], (int, float))
        assert data["duration_seconds"] >= 0.0

    @pytest.mark.asyncio
    async def test_should_emit_zero_usage_when_sanitization_blocks_request(self):
        """Sanitization refusal runs before any LLM call. Usage must be all zeros."""
        blocked = MagicMock()
        blocked.is_safe = False
        blocked.violation = "blocked"
        blocked.sanitized_input = "forbidden"

        with patch(f"{MODULE}.sanitize_input", return_value=blocked):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="forbidden",
                global_variables={},
            )
            events = await _collect_events(gen)

        completes = [e for e in events if '"event": "complete"' in e]
        assert len(completes) == 1
        data = _parse_complete_data(completes[0])
        assert data["usage"] == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        assert "duration_seconds" in data

    @pytest.mark.asyncio
    async def test_should_emit_only_intent_usage_when_intent_is_off_topic(self):
        intent_tokens = {"input_tokens": 9, "output_tokens": 3, "total_tokens": 12}
        mock_classify = AsyncMock(return_value=_make_intent(intent="off_topic", tokens=intent_tokens))

        with patch(f"{MODULE}.classify_intent", mock_classify):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="how does kubernetes work",
                global_variables={},
            )
            events = await _collect_events(gen)

        completes = [e for e in events if '"event": "complete"' in e]
        assert len(completes) == 1
        data = _parse_complete_data(completes[0])
        assert data["usage"] == intent_tokens

    @pytest.mark.asyncio
    async def test_should_not_leak_metrics_key_into_complete_event_data(self):
        """Internal ``_metrics`` envelope must not reach the SSE payload.

        The executor uses ``_metrics`` as the wire between flow_executor and
        the assistant service; only the curated ``usage`` field should reach
        the frontend.
        """
        intent_tokens = {"input_tokens": 5, "output_tokens": 5, "total_tokens": 10}
        agent_tokens = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}

        mock_classify = AsyncMock(return_value=_make_intent(tokens=intent_tokens))
        flow_gen = _make_flow_events([("end", {"result": "hi", "_metrics": agent_tokens})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hi",
                global_variables={},
            )
            events = await _collect_events(gen)

        completes = [e for e in events if '"event": "complete"' in e]
        data = _parse_complete_data(completes[0])
        assert "_metrics" not in data

    @pytest.mark.asyncio
    async def test_should_treat_missing_intent_tokens_as_zero(self):
        """Missing intent tokens must not break per-turn aggregation.

        Older / non-instrumented classifier paths may emit no tokens; the
        agent's call still has to be aggregated without crashing.
        """
        agent_tokens = {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10}
        mock_classify = AsyncMock(return_value=_make_intent(tokens=None))
        flow_gen = _make_flow_events([("end", {"result": "hi", "_metrics": agent_tokens})])

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="hi",
                global_variables={},
            )
            events = await _collect_events(gen)

        completes = [e for e in events if '"event": "complete"' in e]
        data = _parse_complete_data(completes[0])
        assert data["usage"] == agent_tokens
