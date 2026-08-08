"""The Run Flow component must surface the nested-HITL rejection verbatim.

``_run_flow_with_cached_graph`` wraps every failure as ``RuntimeError("Error running
flow: <name>") from None`` — with a flow named "HITL" the user sees "Error running
flow: HITL" and the deliberate guard explanation (move the approval to the parent
flow) is swallowed. The guard's ValueError is a user-facing message and must pass
through unchanged; unexpected errors keep the generic wrapper.
"""

from __future__ import annotations

import pytest
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.graph.base import Graph
from lfx.run.hitl import NESTED_HITL_UNSUPPORTED


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


def _pausing_graph() -> Graph:
    graph = Graph.from_payload(
        {
            "nodes": [
                _node(ChatInput(_id="chat_input")),
                _node(HumanInput(_id="hitl1")),
                _node(ChatOutput(_id="co_approve")),
            ],
            "edges": [
                _edge("chat_input", "hitl1", "message", field="prompt"),
                _edge("hitl1", "co_approve", "branch_approve"),
            ],
        },
        flow_id="sub",
    )
    graph.prepare()
    return graph


class _StubbedRunFlow(RunFlowBaseComponent):
    async def get_graph(self, **_kwargs) -> Graph:
        return _pausing_graph()

    def _build_flow_tweak_data(self) -> dict:
        return {}

    def _build_inputs(self, _tweaks) -> dict:
        return {"input_value": "hi"}


async def test_nested_hitl_rejection_is_surfaced_verbatim():
    component = _StubbedRunFlow()
    component.flow_name_selected = "HITL"
    component.flow_id_selected = "sub"
    component.session_id = "s1"

    with pytest.raises(ValueError, match="parent flow") as excinfo:
        await component._run_flow_with_cached_graph(user_id="u1")

    assert str(excinfo.value) == NESTED_HITL_UNSUPPORTED
