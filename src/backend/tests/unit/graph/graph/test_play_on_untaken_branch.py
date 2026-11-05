"""Play on a component below a branch the router did not take.

The editor builds only the clicked component and its predecessors
(``stop_component_id``). When the router sends the input elsewhere, the clicked
component never runs; the canvas explains why from the router's
``inactivated_vertices`` (``build.py`` reports ``inactivated_vertices`` together
with ``conditionally_excluded_vertices``). These tests pin that the clicked
component is in that set for every branching mode.
"""

from lfx.graph.graph.base import Graph

from tests.unit.graph.graph.test_smart_router_branch_isolation import (
    _TWO_ROUTES,
    RecordingSink,
    _decision_graph,
    _decision_result,
    _make_if_else_router,
    _make_router,
    _StubbedSmartRouter,
)


async def _play(graph: Graph, clicked: str) -> set[str]:
    """Run the router and return the vertices it reports as not taken."""
    graph.prepare(stop_component_id=clicked)
    async for result in graph.async_start():
        vertex = getattr(result, "vertex", None)
        if vertex is not None and vertex.id == "router":
            return graph.inactivated_vertices | graph.conditionally_excluded_vertices
    return set()


def _two_sink_graph(router) -> Graph:
    graph = Graph()
    graph.add_component(router, "router")
    graph.add_component(RecordingSink(_id="taken"), "taken")
    graph.add_component(RecordingSink(_id="untaken"), "untaken")
    return graph


async def test_should_report_clicked_if_else_branch_as_inactive_when_router_takes_the_other():
    graph = _two_sink_graph(_make_if_else_router())
    graph.add_component_edge("router", ("true_result", "input_value"), "taken")
    graph.add_component_edge("router", ("false_result", "input_value"), "untaken")

    reported = await _play(graph, "untaken")

    assert "untaken" in reported
    assert "taken" not in reported


async def test_should_report_clicked_language_model_route_as_inactive_when_router_takes_the_other():
    graph = _two_sink_graph(_make_router(_StubbedSmartRouter, _TWO_ROUTES))
    graph.add_component_edge("router", ("category_1_result", "input_value"), "taken")
    graph.add_component_edge("router", ("category_2_result", "input_value"), "untaken")

    reported = await _play(graph, "untaken")

    assert "untaken" in reported
    assert "taken" not in reported


async def test_should_report_clicked_decision_route_as_inactive_when_router_takes_the_other(monkeypatch):
    monkeypatch.setattr(
        "lfx.components.llm_operations.llm_conditional_router.evaluate_decision",
        lambda *_args, **_kwargs: _decision_result(0.8, 0.2),
    )
    graph, _, _ = _decision_graph()

    reported = await _play(graph, "negative")

    assert "negative" in reported
    assert "positive" not in reported
