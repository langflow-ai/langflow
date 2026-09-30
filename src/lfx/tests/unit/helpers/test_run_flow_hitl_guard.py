"""A nested flow run (Run Flow / Sub Flow / flow-as-tool) must reject a pausing flow loudly.

``lfx.helpers.flow.run_flow`` drives the subgraph via ``graph.arun`` — no pause seam, no
checkpoint — so a Human Input node inside it would silently NOT pause: it yields an empty
message and the run continues down every branch. Mirroring the v1 API guard (LE-1697),
the nested run must fail with a clear error instead, pointing the approval to the parent
flow. An unwired Human Input (no downstream consumer) skips at runtime and stays allowed.
"""

from __future__ import annotations

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.helpers.flow import run_flow


def _node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str, handle: str, field: str = "input_value") -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{handle}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": handle, "output_types": ["Message"]},
            "targetHandle": {"fieldName": field, "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


def _graph(nodes: list[dict], edges: list[dict]) -> Graph:
    graph = Graph.from_payload({"nodes": nodes, "edges": edges}, flow_id="sub")
    graph.prepare()
    return graph


def _pausing_graph() -> Graph:
    return _graph(
        [
            _node(ChatInput(_id="chat_input")),
            _node(HumanInput(_id="hitl1")),
            _node(ChatOutput(_id="co_approve")),
        ],
        [
            _edge("chat_input", "hitl1", "message", field="prompt"),
            _edge("hitl1", "co_approve", "branch_approve"),
        ],
    )


async def test_nested_run_of_pausing_flow_raises_clear_error():
    graph = _pausing_graph()

    with pytest.raises(ValueError, match="Human"):
        await run_flow(inputs={"input_value": "hi"}, user_id="u1", graph=graph)


async def test_nested_run_error_points_to_the_parent_flow():
    graph = _pausing_graph()

    with pytest.raises(ValueError, match="parent flow"):
        await run_flow(inputs={"input_value": "hi"}, user_id="u1", graph=graph)


async def test_unwired_human_input_is_allowed():
    # An isolated Human Input (no downstream consumer) is skipped at runtime, so the
    # nested run is not blocking and must keep working.
    graph = _graph(
        [
            _node(ChatInput(_id="chat_input")),
            _node(ChatOutput(_id="chat_output")),
            _node(HumanInput(_id="hitl_isolated")),
        ],
        [_edge("chat_input", "chat_output", "message")],
    )

    outputs = await run_flow(inputs={"input_value": "hi"}, user_id="u1", graph=graph)

    assert outputs is not None


async def test_plain_flow_still_runs():
    graph = _graph(
        [_node(ChatInput(_id="chat_input")), _node(ChatOutput(_id="chat_output"))],
        [_edge("chat_input", "chat_output", "message")],
    )

    outputs = await run_flow(inputs={"input_value": "hi"}, user_id="u1", graph=graph)

    assert outputs is not None
