"""Execute connected graphs and compare terminal metadata with the graph API."""

import json

from langflow.api.build import _output_meta_for_vertex


async def test_connected_branch_metadata_matches_graph_terminal_nodes():
    """Execute real routing components and compare terminal metadata to the graph API."""
    from lfx.graph import Graph

    from tests.unit.graph.graph.test_smart_router_branch_isolation import RecordingSink, _make_if_else_router

    graph = Graph()
    graph.add_component(_make_if_else_router(), "router")
    graph.add_component(RecordingSink(_id="taken"), "taken")
    graph.add_component(RecordingSink(_id="untaken"), "untaken")
    graph.add_component_edge("router", ("true_result", "input_value"), "taken")
    graph.add_component_edge("router", ("false_result", "input_value"), "untaken")
    graph.prepare()
    seen = []
    async for result in graph.async_start():
        vertex = getattr(result, "vertex", None)
        if vertex is None:
            continue
        meta = _output_meta_for_vertex(graph, vertex.id)
        assert meta["is_terminal"] == (vertex.id in graph.get_terminal_nodes())
        seen.append(vertex.id)
    assert "taken" in seen
    assert "untaken" not in seen


async def test_loop_execution_metadata_matches_graph_terminal_nodes(active_user):
    """Loop fixture execution retains the same terminal selection as the full graph API."""
    from pathlib import Path
    from uuid import uuid4

    from lfx.graph import Graph

    payload = json.loads((Path(__file__).parents[1] / "data" / "LoopTest.json").read_text())
    graph = Graph.from_payload(payload.get("data", payload), flow_id=str(uuid4()), user_id=str(active_user.id))
    graph.prepare()
    completed = 0
    async for result in graph.async_start():
        vertex = getattr(result, "vertex", None)
        if vertex is None:
            continue
        meta = _output_meta_for_vertex(graph, vertex.id)
        assert meta["is_terminal"] == (vertex.id in graph.get_terminal_nodes())
        completed += 1
    assert completed > 0
