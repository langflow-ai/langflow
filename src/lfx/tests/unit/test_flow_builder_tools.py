"""Tests for flow_builder_tools components."""

import asyncio

from lfx.mcp.flow_builder_tools import (
    AddComponent,
    BuildFlowFromSpec,
    ConnectComponents,
    DescribeComponentType,
    SearchComponentTypes,
    drain_flow_events,
    get_working_flow,
    init_working_flow,
    reset_working_flow,
)


class TestSearchComponentTypes:
    def test_search_returns_results(self):
        comp = SearchComponentTypes()
        comp.set(query="Chat")
        result = comp.search_components()
        assert result.data["count"] > 0
        types = {r["type"] for r in result.data["results"]}
        assert "ChatInput" in types

    def test_search_no_query_returns_all(self):
        comp = SearchComponentTypes()
        comp.set(query="")
        result = comp.search_components()
        assert result.data["count"] > 100


class TestDescribeComponentType:
    def test_describe_known_component(self):
        comp = DescribeComponentType()
        comp.set(component_type="ChatInput")
        result = comp.describe_component()
        assert result.data["type"] == "ChatInput"
        assert "outputs" in result.data

    def test_describe_unknown_component(self):
        comp = DescribeComponentType()
        comp.set(component_type="TotallyFakeComponent")
        result = comp.describe_component()
        assert "error" in result.data


class TestBuildFlowFromSpec:
    def test_build_success_returns_text(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Test\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value")
        result = comp.build_flow()
        assert "built successfully" in result.data["text"]
        assert "flow" in result.data

    def test_build_error_returns_text(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Bad\nnodes:\n  A: FakeComponent")
        result = comp.build_flow()
        assert "failed" in result.data["text"].lower()
        assert "error" in result.data

    def test_build_pushes_set_flow_event(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Test\nnodes:\n  A: ChatInput\n  B: ChatOutput\nedges:\n  A.message -> B.input_value")
        comp.build_flow()

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "set_flow"
        assert "flow" in events[0]

    def test_build_error_does_not_push_event(self):
        reset_working_flow()
        comp = BuildFlowFromSpec()
        comp.set(spec="name: Bad\nnodes:\n  A: FakeComponent")
        comp.build_flow()

        events = drain_flow_events()
        assert len(events) == 0


class TestAddComponent:
    def test_add_component_pushes_event(self):
        reset_working_flow()
        comp = AddComponent()
        comp.set(component_type="ChatInput")
        result = comp.add_component()
        assert "id" in result.data
        assert "ChatInput" in result.data["id"]

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "add_component"
        assert "node" in events[0]

    def test_add_unknown_component_returns_error(self):
        reset_working_flow()
        comp = AddComponent()
        comp.set(component_type="TotallyFake")
        result = comp.add_component()
        assert "error" in result.data


class TestConnectComponents:
    def test_connect_pushes_event(self):
        reset_working_flow()

        # Add two components first
        add1 = AddComponent()
        add1.set(component_type="ChatInput")
        r1 = add1.add_component()

        add2 = AddComponent()
        add2.set(component_type="ChatOutput")
        r2 = add2.add_component()

        drain_flow_events()  # clear add events

        conn = ConnectComponents()
        conn.set(
            source_id=r1.data["id"],
            source_output="message",
            target_id=r2.data["id"],
            target_input="input_value",
        )
        result = conn.connect_components()
        assert "Connected" in result.data["text"]

        events = drain_flow_events()
        assert len(events) == 1
        assert events[0]["action"] == "connect"
        assert "edge" in events[0]


class TestContextVarIsolation:
    """Verify that concurrent async tasks get isolated working flow state."""

    async def test_concurrent_tasks_have_isolated_state(self):
        """Two tasks running in parallel should not see each other's working flow."""
        results: dict[str, dict | None] = {}
        a_ready = asyncio.Event()
        b_ready = asyncio.Event()

        async def task_a():
            init_working_flow({"name": "flow_a", "data": {"nodes": [], "edges": []}}, "id_a")
            a_ready.set()
            await b_ready.wait()  # wait for task_b to init its flow
            # After task_b has set its own flow, task_a should still see flow_a
            flow = get_working_flow()
            results["a"] = flow
            events_before = drain_flow_events()
            results["a_events_before"] = len(events_before)
            # Add an event in task_a's context
            comp = AddComponent()
            comp.set(component_type="ChatInput")
            comp.add_component()
            results["a_events_after"] = len(drain_flow_events())
            reset_working_flow()

        async def task_b():
            init_working_flow({"name": "flow_b", "data": {"nodes": [], "edges": []}}, "id_b")
            b_ready.set()
            await a_ready.wait()  # wait for task_a to init its flow
            flow = get_working_flow()
            results["b"] = flow
            results["b_events_before"] = len(drain_flow_events())
            reset_working_flow()

        await asyncio.gather(task_a(), task_b())

        # Each task should have seen its own flow, not the other's
        assert results["a"]["name"] == "flow_a"
        assert results["b"]["name"] == "flow_b"
        # Events should be isolated too
        assert results["a_events_before"] == 0
        assert results["b_events_before"] == 0
        assert results["a_events_after"] == 1  # only task_a's AddComponent event
