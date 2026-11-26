"""Each asking Agent in a run keeps its own approval state, and a run paused before that still resumes.

Real Agents with a scripted model, driven by the CLI HITL driver over a SQLite store.
"""

from __future__ import annotations

import sqlite3
import sys
from itertools import pairwise
from pathlib import Path

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.checkpoint.store import set_default_checkpoint_store
from lfx.run.hitl import request_id_targets_vertex, run_graph_with_human_input
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore

sys.path.insert(0, str(Path(__file__).parent))
from _pause_flows import ScriptedAgent, edge, graph_from, node, payload


@pytest.fixture
def store(tmp_path):
    """A durable store for graph checkpoints and, as the default store, for Agent approval state."""
    store = SqliteCheckpointStore(tmp_path / "checkpoints.sqlite")
    set_default_checkpoint_store(store)
    yield store
    set_default_checkpoint_store(None)


def _agents_payload(*agent_ids: str) -> dict:
    """Chat Input -> each asking Agent in turn -> Chat Output."""
    chain = ["c_in", *agent_ids, "c_out"]
    nodes = [
        node(ChatInput(_id="c_in", should_store_message=False)),
        *(node(ScriptedAgent(_id=agent_id, tool_policy="ask")) for agent_id in agent_ids),
        node(ChatOutput(_id="c_out", should_store_message=False)),
    ]
    edges = [edge(source, target, "message" if source == "c_in" else "response") for source, target in pairwise(chain)]
    return payload(nodes, edges)


async def _drive(graph, store, on_pause=None):
    requests: list[dict] = []

    async def provider(request: dict) -> dict:
        requests.append(request)
        if on_pause is not None:
            on_pause()
        return {"action_id": "approve", "values": {}}

    graph.user_id, graph.session_id, graph.job_id = "u1", "sess", "job-1"
    graph.set_run_id("job-1")
    results = await run_graph_with_human_input(graph, decision_provider=provider, store=store, input_value="hello")
    return requests, {r.vertex.id: r.vertex.built_object for r in results}


async def test_two_asking_agents_each_ask_for_their_own_tool_call(store):
    requests, outputs = await _drive(graph_from(_agents_payload("agent_a", "agent_b")), store)

    # The second Agent used to load the first one's finished run and answer from its tool result.
    assert [
        [agent for agent in ("agent_a", "agent_b") if request_id_targets_vertex(r["request_id"], agent, "job-1")]
        for r in requests
    ] == [["agent_a"], ["agent_b"]]
    assert outputs["c_out"]["message"].get_text() == "done:effect"


async def test_an_agent_paused_under_the_shared_key_resumes(tmp_path, store):
    def move_to_the_shared_key() -> None:
        # How a run paused before this change stored it: one blob for the whole run, kind "agent".
        with sqlite3.connect(tmp_path / "checkpoints.sqlite") as conn:
            conn.execute("UPDATE checkpoint_blobs SET kind = 'agent' WHERE job_id = 'job-1'")

    requests, outputs = await _drive(graph_from(_agents_payload("agent_a")), store, move_to_the_shared_key)

    # The resumed Agent found its pending approval: it ran the tool and did not ask again.
    assert len(requests) == 1
    assert outputs["c_out"]["message"].get_text() == "done:effect"
