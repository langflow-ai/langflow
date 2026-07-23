"""Engine-side persistence of resolved HumanInput branch decisions (multi-HITL fix).

A HumanInput stops its non-chosen branches with ``self.stop()`` (transient INACTIVE: reset per
build, never checkpointed). When a later HumanInput pauses, an earlier node's dead branches would
revive on resume and execute -- surfacing extra Chat Outputs and re-pausing the first node. The
graph promotes each already-answered decision into the durable ``conditionally_excluded_vertices``
channel at pause time, derived from edges + the decision.

The graph is assembled from real components (so the dynamic ``branch_*`` outputs and edges are the
real ones) rather than a saved-flow fixture.
"""

from __future__ import annotations

import json

from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.checkpoint.resume import compute_resume_layer
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.graph.base import Graph

FIRST_HITL = "hitl1"
APPROVE_TARGET = "co_approve"
DEAD_TARGETS = {"co_reject"}


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


def _build_graph() -> Graph:
    """Chat Input -> HumanInput -> {branch_approve: co_approve, branch_reject: co_reject}."""
    payload = {
        "nodes": [
            _node(ChatInput(_id="chat_input")),
            _node(HumanInput(_id=FIRST_HITL)),
            _node(ChatOutput(_id=APPROVE_TARGET)),
            _node(ChatOutput(_id="co_reject")),
        ],
        "edges": [
            _edge("chat_input", FIRST_HITL, "message", field="prompt"),
            _edge(FIRST_HITL, APPROVE_TARGET, "branch_approve"),
            _edge(FIRST_HITL, "co_reject", "branch_reject"),
        ],
    }
    graph = Graph.from_payload(payload, flow_id="f1")
    graph.prepare()
    graph.set_run_id("RUN1")
    return graph


def test_resolved_decision_excludes_only_dead_branches():
    graph = _build_graph()
    graph.human_input_decisions = {f"{FIRST_HITL}:RUN1": {"action_id": "approve"}}

    graph._persist_resolved_branch_exclusions()

    assert graph.conditionally_excluded_vertices == DEAD_TARGETS
    assert APPROVE_TARGET not in graph.conditionally_excluded_vertices


def test_no_decision_excludes_nothing():
    graph = _build_graph()

    graph._persist_resolved_branch_exclusions()

    assert graph.conditionally_excluded_vertices == set()


def test_exclusion_survives_checkpoint_round_trip_and_resume():
    graph = _build_graph()
    graph.checkpointing_enabled = True
    graph.human_input_decisions = {f"{FIRST_HITL}:RUN1": {"action_id": "approve"}}
    graph._persist_resolved_branch_exclusions()

    checkpoint = graph.build_checkpoint()
    restored_cp = GraphCheckpoint.model_validate(json.loads(checkpoint.model_dump_json()))
    assert set(restored_cp.conditionally_excluded_vertices) == DEAD_TARGETS

    resumed = Graph.resume_from_checkpoint(restored_cp)
    assert resumed.conditionally_excluded_vertices == DEAD_TARGETS
    layer = compute_resume_layer(resumed)
    for dead in DEAD_TARGETS:
        assert dead not in layer
