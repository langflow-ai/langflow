"""Tests for restore-point orchestration in the assistant streaming pipeline.

A canvas-mutating turn (build_flow / component_then_flow) must snapshot the
flow BEFORE the agent runs and surface the version id additively on the SSE
``complete`` event as ``restore_version_id``. Plain questions and run-only
turns never snapshot, and a snapshot failure never breaks the stream.
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult

MODULE = "langflow.agentic.services.assistant_service"

FLOW_ID = str(uuid4())
USER_ID = str(uuid4())


def _make_intent(intent="question", translation="test"):
    return IntentResult(intent=intent, translation=translation)


def _make_flow_events(events):
    async def gen():
        for event_type, event_data in events:
            yield event_type, event_data

    return gen


def _parse_events(events):
    return [json.loads(e.removeprefix("data: ").strip()) for e in events]


async def _run_stream(*, intent, restore_mock, drain_side_effect=None, input_value="build me a flow"):
    flow_gen = _make_flow_events([("end", {"result": "done"})])
    with ExitStack() as stack:
        stack.enter_context(
            patch(f"{MODULE}.classify_intent", new_callable=AsyncMock, return_value=_make_intent(intent))
        )
        stack.enter_context(patch(f"{MODULE}.execute_flow_file_streaming", side_effect=lambda **_kw: flow_gen()))
        stack.enter_context(patch(f"{MODULE}._get_current_flow_summary", new_callable=AsyncMock, return_value=None))
        stack.enter_context(patch(f"{MODULE}.create_restore_point", restore_mock))
        if drain_side_effect is not None:
            stack.enter_context(patch(f"{MODULE}.drain_flow_events", side_effect=drain_side_effect))
        gen = execute_flow_with_validation_streaming(
            flow_filename="TestFlow",
            input_value=input_value,
            global_variables={"FLOW_ID": FLOW_ID},
            user_id=USER_ID,
        )
        return [event async for event in gen]


class TestRestorePointCreation:
    @pytest.mark.asyncio
    async def test_should_create_restore_point_for_build_flow_intent(self):
        restore_mock = AsyncMock(return_value="version-abc")
        events = await _run_stream(
            intent="build_flow",
            restore_mock=restore_mock,
            drain_side_effect=[[{"action": "add_component", "node": {"id": "n1"}}]] + [[]] * 10,
        )

        restore_mock.assert_awaited_once_with(FLOW_ID, USER_ID)
        completes = [p for p in _parse_events(events) if p.get("event") == "complete"]
        assert len(completes) == 1
        assert completes[0]["data"]["restore_version_id"] == "version-abc"

    @pytest.mark.asyncio
    async def test_should_create_restore_point_for_compound_intent(self):
        restore_mock = AsyncMock(return_value="version-xyz")
        events = await _run_stream(
            intent="component_then_flow",
            restore_mock=restore_mock,
            drain_side_effect=[[{"action": "set_flow"}]] + [[]] * 10,
        )

        restore_mock.assert_awaited_once_with(FLOW_ID, USER_ID)
        completes = [p for p in _parse_events(events) if p.get("event") == "complete"]
        assert completes
        assert completes[0]["data"]["restore_version_id"] == "version-xyz"


class TestRestorePointSkips:
    @pytest.mark.asyncio
    async def test_should_not_create_restore_point_for_question_intent(self):
        restore_mock = AsyncMock(return_value="never-used")
        events = await _run_stream(intent="question", restore_mock=restore_mock, input_value="what is langflow?")

        restore_mock.assert_not_awaited()
        completes = [p for p in _parse_events(events) if p.get("event") == "complete"]
        assert completes
        assert "restore_version_id" not in completes[0]["data"]

    @pytest.mark.asyncio
    async def test_should_not_create_restore_point_for_run_flow_intent(self):
        restore_mock = AsyncMock(return_value="never-used")
        await _run_stream(intent="run_flow", restore_mock=restore_mock, input_value="run the flow")

        restore_mock.assert_not_awaited()


class TestRestorePointFailureTolerance:
    @pytest.mark.asyncio
    async def test_should_complete_the_turn_when_restore_point_raises(self):
        restore_mock = AsyncMock(side_effect=RuntimeError("versioning blew up"))
        events = await _run_stream(
            intent="build_flow",
            restore_mock=restore_mock,
            drain_side_effect=[[{"action": "add_component", "node": {"id": "n1"}}]] + [[]] * 10,
        )

        restore_mock.assert_awaited_once()
        parsed = _parse_events(events)
        completes = [p for p in parsed if p.get("event") == "complete"]
        assert len(completes) == 1, f"Turn must complete despite snapshot failure. Events: {events}"
        assert "restore_version_id" not in completes[0]["data"]
        assert not any(p.get("event") == "error" for p in parsed)

    @pytest.mark.asyncio
    async def test_should_omit_field_when_restore_point_returns_none(self):
        restore_mock = AsyncMock(return_value=None)
        events = await _run_stream(
            intent="build_flow",
            restore_mock=restore_mock,
            drain_side_effect=[[{"action": "add_component", "node": {"id": "n1"}}]] + [[]] * 10,
        )

        completes = [p for p in _parse_events(events) if p.get("event") == "complete"]
        assert completes
        assert "restore_version_id" not in completes[0]["data"]
