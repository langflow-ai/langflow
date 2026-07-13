"""An orphaned tool-mode component must not be built standalone.

A component in ``tool_mode`` only makes sense wired as a tool into an Agent (its output is a Tool
object, not a flow result). Left in a flow with no consumer -- e.g. a URL/Calculator tool after its
Agent was deleted -- it used to be scheduled and executed on its own, throwing a ComponentBuildError
(``No valid URLs provided``) that failed the whole run. It must be skipped instead, while the rest
of the flow stays runnable.

The graph is assembled from real components so ``tool_mode`` and the edge topology are real.
"""

from __future__ import annotations

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph

ORPHANED_TOOL = "orphan_tool"


def _node(component, *, tool_mode: bool = False) -> dict:
    frontend = component.to_frontend_node()
    if tool_mode:
        frontend["data"]["node"]["tool_mode"] = True
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str) -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": "message", "output_types": ["Message"]},
            "targetHandle": {"fieldName": "input_value", "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


def _prepared_graph() -> Graph:
    """Chat Input -> Chat Output, plus a tool-mode node with no consumer (the orphan)."""
    payload = {
        "nodes": [
            _node(ChatInput(_id="chat_input")),
            _node(ChatOutput(_id="chat_output")),
            _node(ChatOutput(_id=ORPHANED_TOOL), tool_mode=True),
        ],
        "edges": [_edge("chat_input", "chat_output")],
    }
    graph = Graph.from_payload(payload, flow_id="f1")
    graph.prepare()
    return graph


def test_orphaned_tool_mode_node_excluded_from_run():
    graph = _prepared_graph()

    assert ORPHANED_TOOL not in graph.vertices_to_run
    assert ORPHANED_TOOL not in graph._first_layer
    assert all(ORPHANED_TOOL not in layer for layer in graph.vertices_layers)


def test_non_tool_nodes_still_run():
    graph = _prepared_graph()

    assert "chat_input" in graph.vertices_to_run
    assert "chat_output" in graph.vertices_to_run


def test_orphaned_tool_excluded_from_resume_layer():
    # The resume path schedules via compute_resume_layer, not sort_vertices; the orphan (no
    # predecessors, unbuilt) would otherwise be re-queued on every HITL resume and crash the run.
    graph = _prepared_graph()
    graph.set_run_id()

    assert ORPHANED_TOOL not in graph.resume_first_layer()


async def test_run_completes_despite_orphaned_tool():
    graph = _prepared_graph()
    graph.set_run_id()

    results = await graph.arun([{}], fallback_to_env_vars=False)

    assert results is not None
    assert not graph.get_vertex(ORPHANED_TOOL).built
