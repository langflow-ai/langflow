"""Play on a component below a branch the router did not take.

The editor builds only the clicked component and its predecessors
(``stop_component_id``). When the router sends the input elsewhere, the clicked
component never runs; the canvas explains why from what ``build.py`` reports:
the vertex in ``inactivated_vertices`` and, in ``branch_skips``, the router that
excluded it and the outputs that router took. These tests run each routing mode
through ``AGUITranslator`` and check the ``inactive`` op the canvas reads.
"""

from lfx.graph.graph.base import Graph
from lfx.workflow.agui_translator import AGUITranslator

from tests.unit.graph.graph.test_smart_router_branch_isolation import (
    _TWO_ROUTES,
    RecordingSink,
    _decision_graph,
    _decision_result,
    _ElseSmartRouter,
    _make_if_else_router,
    _make_router,
    _StubbedSmartRouter,
)


async def _play(graph: Graph, clicked: str) -> dict[str, dict]:
    """Run the router and return the ``inactive`` op values the canvas receives, by node."""
    graph.prepare(stop_component_id=clicked)
    async for result in graph.async_start():
        vertex = getattr(result, "vertex", None)
        if vertex is not None and vertex.id == "router":
            build_data = {
                "id": "router",
                "valid": True,
                "data": None,
                "inactivated_vertices": list(graph.inactivated_vertices | graph.conditionally_excluded_vertices),
                "branch_skips": graph.branch_skips(),
            }
            translator = AGUITranslator(run_id="run", thread_id="thread")
            translator.start()
            delta = translator.translate("end_vertex", {"build_data": build_data})[1].delta
            return {
                op["path"].removeprefix("/nodes/"): op["value"] for op in delta if op["value"]["status"] == "inactive"
            }
    return {}


def _two_sink_graph(router) -> Graph:
    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(RecordingSink(_id="taken"), "taken")
    graph.add_component(RecordingSink(_id="untaken"), "untaken")
    return graph


async def test_should_name_the_if_else_output_taken_when_play_is_on_the_other_branch():
    graph = _two_sink_graph(_make_if_else_router())
    graph.add_component_edge("router", ("true_result", "input_value"), "taken")
    graph.add_component_edge("router", ("false_result", "input_value"), "untaken")

    inactive = await _play(graph, "untaken")

    assert inactive["untaken"]["skipped_by"] == "router"
    assert inactive["untaken"]["taken_outputs"] == ["true_result"]
    assert "taken" not in inactive


async def test_should_name_the_language_model_route_taken_when_play_is_on_the_other_route():
    graph = _two_sink_graph(_make_router(_StubbedSmartRouter, _TWO_ROUTES))
    graph.add_component_edge("router", ("category_1_result", "input_value"), "taken")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "untaken")

    inactive = await _play(graph, "untaken")

    assert inactive["untaken"]["skipped_by"] == "router"
    assert inactive["untaken"]["taken_outputs"] == ["category_1_result"]


async def test_should_not_name_an_unconnected_else_the_router_did_not_take():
    router = _make_router(_ElseSmartRouter, _TWO_ROUTES, enable_else_output=True)
    graph = _two_sink_graph(router)
    graph.add_component_edge("router", ("category_1_result", "input_value"), "taken")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "untaken")

    inactive = await _play(graph, "untaken")

    assert inactive["untaken"]["taken_outputs"] == ["category_1_result"]


async def test_should_name_the_decision_route_taken_when_play_is_on_the_other_route(monkeypatch):
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: _decision_result(0.8, 0.2),
    )
    graph, _, _ = _decision_graph()

    inactive = await _play(graph, "negative")

    assert inactive["negative"]["skipped_by"] == "router"
    assert inactive["negative"]["taken_outputs"] == ["category_1_result"]
    assert "positive" not in inactive
