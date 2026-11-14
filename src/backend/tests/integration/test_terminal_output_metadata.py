"""Execute connected graphs and verify terminal metadata at the output-event boundary."""

import json

from langflow.api.build import _output_meta_for_vertex

from tests.unit.api.v2.test_output_event_parity import _adapter, _end_vertex_data


async def test_connected_branch_metadata_matches_terminal_output_events():
    """Execute real routing components and compare terminal events to the graph API."""
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
        data = _end_vertex_data(vertex.id, "result", is_terminal=meta["is_terminal"])
        data["output_meta"] = meta
        events = list(_adapter().translate("end_vertex", data))
        assert any(event.type == "output" for event in events) == meta["is_terminal"]
        seen.append(vertex.id)
    assert "taken" in seen
    assert "untaken" not in seen


async def test_loop_execution_metadata_matches_terminal_output_events(active_user):
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
        data = _end_vertex_data(vertex.id, "result", is_terminal=meta["is_terminal"])
        data["output_meta"] = meta
        events = list(_adapter().translate("end_vertex", data))
        assert any(event.type == "output" for event in events) == meta["is_terminal"]
        completed += 1
    assert completed > 0
