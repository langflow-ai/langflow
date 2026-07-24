"""Tests for the live ``tool_start`` SSE indicator.

Canvas-mutating flow-builder tools must announce the moment they START
executing (through the per-context listener installed by the streaming
executor) BEFORE their ``flow_update`` lands in the drain queue, so the
frontend can show a "currently doing X" row while the tool runs. Read-only
tools must stay silent.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from langflow.agentic.helpers.sse import format_tool_start_event
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_types import IntentResult
from lfx.mcp.flow_builder_tools import (
    BuildFlowFromSpec,
    ConfigureComponent,
    ConnectComponents,
    RemoveComponent,
    SearchComponentTypes,
    drain_flow_events,
    emit_tool_start,
    init_working_flow,
    isolate_flow_run_context,
    reset_working_flow,
    set_tool_start_listener,
)
from lfx.schema import Data

MODULE = "langflow.agentic.services.assistant_service"


@pytest.fixture(autouse=True)
def _clean_tool_state():
    reset_working_flow()
    yield
    set_tool_start_listener(None)
    reset_working_flow()


def _capture_tool_starts() -> list[dict]:
    """Record each payload plus the flow_updates queued at emission time.

    An empty ``pending_flow_updates`` proves tool_start fired BEFORE the
    tool's own flow_update landed.
    """
    captured: list[dict] = []

    def listener(payload: dict) -> None:
        captured.append({"payload": payload, "pending_flow_updates": drain_flow_events()})

    set_tool_start_listener(listener)
    return captured


def _flow_with_node(node_id: str = "ChatInput-abc", node_type: str = "ChatInput") -> dict:
    return {
        "name": "Test Flow",
        "data": {
            "nodes": [
                {
                    "data": {
                        "id": node_id,
                        "type": node_type,
                        "node": {"template": {"input_value": {"value": "", "type": "str"}}},
                    }
                }
            ],
            "edges": [],
        },
    }


class TestMutatingToolsEmitToolStart:
    def test_remove_component_emits_tool_start_before_its_flow_update(self):
        init_working_flow(_flow_with_node())
        captured = _capture_tool_starts()

        comp = RemoveComponent()
        comp.set(component_id="ChatInput-abc")
        result = comp.remove_component()

        assert isinstance(result, Data)
        assert len(captured) == 1
        assert captured[0]["payload"] == {"tool": "remove_component", "component_id": "ChatInput-abc"}
        assert captured[0]["pending_flow_updates"] == []
        completed = drain_flow_events()
        assert any(e["action"] == "remove_component" for e in completed)

    def test_configure_component_emits_tool_start_before_its_flow_update(self):
        init_working_flow(_flow_with_node())
        captured = _capture_tool_starts()

        comp = ConfigureComponent()
        comp.set(component_id="ChatInput-abc", params='{"input_value": "hello"}')
        result = comp.configure_component()

        assert "error" not in result.data
        assert len(captured) == 1
        assert captured[0]["payload"] == {"tool": "configure_component", "component_id": "ChatInput-abc"}
        assert captured[0]["pending_flow_updates"] == []
        completed = drain_flow_events()
        assert any(e["action"] == "configure" for e in completed)

    def test_connect_components_emits_tool_start_even_when_connection_fails(self):
        init_working_flow(_flow_with_node())
        captured = _capture_tool_starts()

        comp = ConnectComponents()
        comp.set(
            source_id="ChatInput-abc",
            source_output="message",
            target_id="Missing-xyz",
            target_input="input_value",
        )
        result = comp.connect_components()

        assert "error" in result.data
        assert len(captured) == 1
        assert captured[0]["payload"]["tool"] == "connect_components"
        assert captured[0]["payload"]["source_id"] == "ChatInput-abc"
        assert captured[0]["payload"]["target_id"] == "Missing-xyz"

    def test_build_flow_emits_tool_start(self):
        captured = _capture_tool_starts()

        comp = BuildFlowFromSpec()
        comp.set(spec="not a valid spec")
        comp.build_flow()

        assert len(captured) == 1
        assert captured[0]["payload"] == {"tool": "build_flow"}


class TestReadOnlyToolsStaySilent:
    def test_search_components_does_not_emit_tool_start(self):
        captured = _capture_tool_starts()

        comp = SearchComponentTypes()
        comp.set(query="Chat")
        result = comp.search_components()

        assert result.data["count"] > 0
        assert captured == []
        assert drain_flow_events() == []


class TestListenerRobustness:
    def test_listener_exception_does_not_break_the_tool(self):
        init_working_flow(_flow_with_node())

        def exploding_listener(_payload: dict) -> None:
            msg = "listener blew up"
            raise RuntimeError(msg)

        set_tool_start_listener(exploding_listener)
        comp = RemoveComponent()
        comp.set(component_id="ChatInput-abc")
        result = comp.remove_component()

        assert result.data.get("removed") == "ChatInput-abc"

    def test_emit_is_a_noop_without_listener(self):
        emit_tool_start("add_component", component_type="ChatInput")
        assert drain_flow_events() == []

    def test_isolate_flow_run_context_clears_the_listener(self):
        captured = _capture_tool_starts()
        isolate_flow_run_context()

        emit_tool_start("build_flow")

        assert captured == []


class TestListenerLifecycle:
    """The executor-installed listener must not outlive its run.

    A leaked listener keeps forwarding tool_start payloads onto a finished
    run's event queue from any later work on the same asyncio context.
    """

    @pytest.mark.asyncio
    async def test_run_graph_with_events_clears_listener_when_run_fails(self):
        import asyncio
        from unittest.mock import MagicMock

        from langflow.agentic.services.flow_executor import _run_graph_with_events
        from langflow.agentic.services.flow_types import FlowExecutionResult
        from lfx.events.event_manager import create_default_event_manager

        event_queue: asyncio.Queue = asyncio.Queue()
        event_manager = create_default_event_manager(event_queue)
        graph = MagicMock()
        graph.context = {}
        graph.prepare.side_effect = RuntimeError("boom")
        execution_result = FlowExecutionResult()

        await _run_graph_with_events(
            graph=graph,
            input_value=None,
            global_variables=None,
            user_id=None,
            session_id=None,
            event_manager=event_manager,
            event_queue=event_queue,
            execution_result=execution_result,
        )

        assert execution_result.has_error
        size_after_run = event_queue.qsize()
        emit_tool_start("add_component", component_type="ChatInput")
        assert event_queue.qsize() == size_after_run, "listener leaked past the run"

    @pytest.mark.asyncio
    async def test_run_graph_with_events_clears_listener_after_success(self):
        import asyncio
        from unittest.mock import MagicMock

        from langflow.agentic.services import flow_executor
        from langflow.agentic.services.flow_executor import _run_graph_with_events
        from langflow.agentic.services.flow_types import FlowExecutionResult
        from lfx.events.event_manager import create_default_event_manager

        event_queue: asyncio.Queue = asyncio.Queue()
        event_manager = create_default_event_manager(event_queue)
        graph = MagicMock()
        graph.context = {}
        execution_result = FlowExecutionResult()

        async def empty_stream(*_a, **_kw):
            return
            yield  # pragma: no cover — makes this an async generator

        coordinator = MagicMock()
        coordinator.stream = empty_stream
        with patch.object(flow_executor, "get_default_coordinator", return_value=coordinator):
            await _run_graph_with_events(
                graph=graph,
                input_value=None,
                global_variables=None,
                user_id=None,
                session_id=None,
                event_manager=event_manager,
                event_queue=event_queue,
                execution_result=execution_result,
            )

        size_after_run = event_queue.qsize()
        emit_tool_start("add_component", component_type="ChatInput")
        assert event_queue.qsize() == size_after_run, "listener leaked past the run"


class TestFormatToolStartEvent:
    def test_builds_english_fallback_label_from_tool_and_fields(self):
        event = format_tool_start_event({"tool": "add_component", "component_type": "ChatInput"})
        payload = json.loads(event.removeprefix("data: "))
        assert payload == {
            "event": "tool_start",
            "tool": "add_component",
            "component_type": "ChatInput",
            "label": "Adding ChatInput",
        }

    def test_keeps_caller_provided_label(self):
        event = format_tool_start_event({"tool": "build_flow", "label": "Custom"})
        payload = json.loads(event.removeprefix("data: "))
        assert payload["label"] == "Custom"

    def test_unknown_tool_gets_generic_label(self):
        event = format_tool_start_event({"tool": "future_tool"})
        payload = json.loads(event.removeprefix("data: "))
        assert payload["label"] == "Working"


class TestToolStartStreamsThroughSSE:
    @pytest.mark.asyncio
    async def test_tool_start_is_forwarded_before_the_next_token(self):
        mock_classify = AsyncMock(return_value=IntentResult(intent="question", translation="test"))

        async def flow_gen():
            yield ("tool_start", {"tool": "add_component", "component_type": "ChatInput"})
            yield ("token", "adding it now")
            yield ("end", {"result": "done"})

        with (
            patch(f"{MODULE}.classify_intent", mock_classify),
            patch(f"{MODULE}.execute_flow_file_streaming", return_value=flow_gen()),
        ):
            gen = execute_flow_with_validation_streaming(
                flow_filename="TestFlow",
                input_value="add a chat input",
                global_variables={},
                user_id="user-1",
            )
            events = [event async for event in gen]

        tool_start_idx = next(i for i, e in enumerate(events) if '"event": "tool_start"' in e)
        token_idx = next(i for i, e in enumerate(events) if '"event": "token"' in e)
        assert tool_start_idx < token_idx
        payload = json.loads(events[tool_start_idx].removeprefix("data: "))
        assert payload["tool"] == "add_component"
        assert payload["label"] == "Adding ChatInput"
