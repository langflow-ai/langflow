"""A resume must never reschedule a vertex the checkpoint restored as built.

``_restore_run_manager`` used to copy ``vertices_to_run`` verbatim from the checkpoint,
so already-built vertices stayed eligible. ``is_vertex_runnable`` does not consult
``built``, so the backward walk that looks for runnable predecessors when a successor
is blocked (``find_runnable_predecessors_for_successor``) could hand an already-built
vertex back to the build loop. For Chat Input that re-executes the component and
persists a second User message for the same turn.
"""

from __future__ import annotations

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.schema.schema import INPUT_FIELD_NAME

CHAT_INPUT = "chat_input"
HITL = "hitl1"


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
    payload = {
        "nodes": [
            _node(ChatInput(_id=CHAT_INPUT)),
            _node(HumanInput(_id=HITL)),
            _node(ChatOutput(_id="co_approve")),
            _node(ChatOutput(_id="co_reject")),
        ],
        "edges": [
            _edge(CHAT_INPUT, HITL, "message", field="prompt"),
            _edge(HITL, "co_approve", "branch_approve"),
            _edge(HITL, "co_reject", "branch_reject"),
        ],
    }
    graph = Graph.from_payload(payload, flow_id="resume-reschedule")
    graph.prepare()
    return graph


@pytest.fixture
async def resumed_graph():
    """The graph a resume hands to the build loop, with the gated vertex un-built."""
    store = InMemoryCheckpointStore()
    graph = _pausing_graph()
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    graph._set_inputs([], {INPUT_FIELD_NAME: "hello"}, "chat")

    with pytest.raises(GraphPausedException):
        await graph.process(fallback_to_env_vars=False)

    checkpoint = await store.load_by_run_id(str(graph.run_id))
    assert checkpoint is not None
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    resumed.get_vertex(HITL).built = False
    return resumed


async def test_built_vertices_are_not_eligible_to_run_again(resumed_graph):
    assert resumed_graph.get_vertex(CHAT_INPUT).built is True
    assert resumed_graph.is_vertex_runnable(CHAT_INPUT) is False


async def test_no_restored_built_vertex_is_runnable(resumed_graph):
    """Generalized: the backward walk can reach any built vertex, not just Chat Input."""
    still_runnable = [v.id for v in resumed_graph.vertices if v.built and resumed_graph.is_vertex_runnable(v.id)]
    assert still_runnable == []


async def test_the_gated_vertex_stays_runnable(resumed_graph):
    """Guards the tempting wrong fix: pruning built vertices from ``vertices_to_run`` at restore.

    The gated node (and opaque-dropped producers) are built at checkpoint time yet MUST re-run,
    so eligibility has to read the live ``built`` flag after the resume un-builds them.
    """
    assert HITL in resumed_graph.run_manager.vertices_to_run
    assert resumed_graph.is_vertex_runnable(HITL) is True
