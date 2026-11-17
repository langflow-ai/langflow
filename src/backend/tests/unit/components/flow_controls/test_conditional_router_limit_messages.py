"""Iteration limits must route the configured message to the default branch."""

import pytest
from lfx.components.flow_controls.conditional_router import ConditionalRouterComponent
from lfx.components.input_output.text import TextInputComponent
from lfx.components.input_output.text_output import TextOutputComponent
from lfx.graph import Graph
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestConditionalRouterIterationLimitMessages(ComponentTestBaseWithoutClient):
    """Iteration limit behaviour of the If-Else component."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return ConditionalRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_text": "test input",
            "operator": "equals",
            "match_text": "test input",
            "case_sensitive": True,
            "true_case_message": Message(text="true result"),
            "false_case_message": Message(text="false result"),
            "max_iterations": 10,
            "default_route": "true_result",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.mark.parametrize("default_route", ["true_result", "false_result"])
    @pytest.mark.parametrize("condition", [True, False])
    @pytest.mark.parametrize("max_iterations", [1, 2])
    @pytest.mark.parametrize("override", ["configured message", ""])
    async def test_iteration_limit_routes_message_to_selected_consumer(
        self, default_route, condition, max_iterations, override
    ):
        """The selected consumer keeps its message when the iteration limit is hit."""
        source = TextInputComponent(_id="source").set(input_value="original input")
        router = ConditionalRouterComponent(_id="router").set(
            input_text=source.text_response,
            match_text="original input" if condition else "different",
            operator="equals",
            max_iterations=max_iterations,
            default_route=default_route,
            true_case_message=override,
            false_case_message=override,
        )
        true_sink = TextOutputComponent(_id="true_sink").set(input_value=router.true_response)
        false_sink = TextOutputComponent(_id="false_sink").set(input_value=router.false_response)
        graph = Graph()
        graph.add_component(true_sink)
        graph.add_component(false_sink)
        graph.prepare(start_component_id=source.get_id())

        results = [result async for result in graph.async_start()]

        selected_true = default_route == "true_result" if max_iterations == 1 else condition
        selected = true_sink if selected_true else false_sink
        rejected = false_sink if selected_true else true_sink
        built_ids = {result.vertex.id for result in results if hasattr(result, "vertex")}
        assert selected.get_id() in built_ids
        assert rejected.get_id() not in built_ids
        assert graph.get_vertex(selected.get_id()).results["text"].text == (override or "original input")
        assert graph.context["router_iteration"] == 1

    @pytest.mark.parametrize("default_route", ["true_result", "false_result"])
    async def test_cycle_break_preserves_default_message(self, default_route):
        """A cycle that hits the iteration limit keeps the default route's message."""
        source = TextInputComponent(_id="cycle_input")
        router = ConditionalRouterComponent(_id="router").set(
            input_text=source.text_response,
            match_text="stop",
            operator="equals" if default_route == "true_result" else "not equals",
            max_iterations=3,
            default_route=default_route,
            true_case_message="finished" if default_route == "true_result" else "keep trying",
            false_case_message="finished" if default_route == "false_result" else "keep trying",
        )
        source.set(input_value=router.false_response if default_route == "true_result" else router.true_response)
        sink = TextOutputComponent(_id="sink").set(
            input_value=router.true_response if default_route == "true_result" else router.false_response
        )
        graph = Graph(start=source, end=sink)

        results = [result async for result in graph.async_start(max_iterations=20, config={"output": {"cache": False}})]

        assert graph.context["router_iteration"] == 3
        assert sum(result.vertex.id == "router" for result in results if hasattr(result, "vertex")) == 3
        assert graph.get_vertex("sink").results["text"].text == "finished"
