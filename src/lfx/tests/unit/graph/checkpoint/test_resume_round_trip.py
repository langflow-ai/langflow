"""End-to-end graph resume round-trip (LE-1449 / LE-1446 mechanics).

A real ChatInput -> StaticPauser -> ChatOutput graph: first run suspends with a
node_input request and a durable checkpoint; resume hydrates the checkpoint,
injects the decision, un-builds the paused node, and runs to completion without
re-executing already-built vertices. This proves the exact resume-from-checkpoint
+ inject + un-build sequence that build.py's resume branch performs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException

sys.path.insert(0, str(Path(__file__).parent))
from _static_pauser import StaticPauser


def _graph(store, *, job_id="job-1"):
    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    pauser = StaticPauser(_id="pauser")
    pauser.set(input_value=chat_input.message_response)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=pauser.run_it, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.session_id = "sess-1"
    graph.set_run_id(job_id)
    graph.job_id = job_id
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    return graph


async def test_first_run_suspends_with_durable_checkpoint():
    store = InMemoryCheckpointStore()
    graph = _graph(store)

    with pytest.raises(GraphPausedException) as excinfo:
        await graph.process(fallback_to_env_vars=False)

    assert excinfo.value.reason == "human_input_required"
    assert excinfo.value.data["request_id"] == "pauser:job-1"
    assert graph.get_vertex("chat_input").built is True
    assert graph.get_vertex("chat_output").built is False
    assert await store.load_by_run_id("job-1") is not None


async def test_resume_injects_decision_runs_to_completion_without_reexec():
    store = InMemoryCheckpointStore()
    first = _graph(store)
    with pytest.raises(GraphPausedException):
        await first.process(fallback_to_env_vars=False)

    # The build.py resume branch performs exactly these four steps:
    checkpoint = await store.load_by_run_id("job-1")
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    resumed.human_input_decisions = {"pauser:job-1": {"action_id": "approve", "values": {}}}
    resumed.get_vertex("pauser").built = False

    assert resumed.resume_first_layer() == ["pauser"]
    assert resumed.get_vertex("chat_input").built is True  # not re-run

    await resumed.process(fallback_to_env_vars=False)

    assert resumed.get_vertex("pauser").built is True
    assert resumed.get_vertex("chat_output").built is True
    pauser_result = resumed.get_vertex("pauser").results
    assert pauser_result["out"].text == "approve"  # the injected decision flowed downstream


async def test_resume_without_decision_suspends_again():
    store = InMemoryCheckpointStore()
    first = _graph(store)
    with pytest.raises(GraphPausedException):
        await first.process(fallback_to_env_vars=False)

    checkpoint = await store.load_by_run_id("job-1")
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    resumed.get_vertex("pauser").built = False  # re-run, but no decision injected

    with pytest.raises(GraphPausedException):
        await resumed.process(fallback_to_env_vars=False)


async def test_resume_restores_user_id_from_checkpoint():
    """A durable run must resume under the identity that started it.

    The checkpoint is written mid-run (user_id already stamped by the initial build), so
    resume must restore graph.user_id too. Without it, a component that reads self.user_id
    on resume — e.g. an A2A Agent tool listing in-project agents under HITL tool-approval —
    resolves it to None via the graph.user_id fallback, and str(None) == "None" is then
    parsed as a UUID: "badly formed hexadecimal UUID string".
    """
    store = InMemoryCheckpointStore()
    first = _graph(store)
    first.user_id = "f7bee55e-6daa-4d9d-916a-2f8783e02ed8"
    with pytest.raises(GraphPausedException):
        await first.process(fallback_to_env_vars=False)

    checkpoint = await store.load_by_run_id("job-1")
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)

    # Root cause: the resumed graph must carry the original identity.
    assert resumed.user_id == "f7bee55e-6daa-4d9d-916a-2f8783e02ed8"
    # Exact A2A failure mechanism: the component's user_id property falls back to
    # graph.user_id, so a restored component (its own _user_id lost) must still resolve it.
    pauser_component = resumed.get_vertex("pauser").custom_component
    assert pauser_component.user_id == "f7bee55e-6daa-4d9d-916a-2f8783e02ed8"


async def test_resume_reapplies_user_id_to_restored_component():
    """A checkpoint-restored component loses _user_id; the build re-applies it on resume.

    Without this, load_from_db fields (e.g. an Agent's API key global variable) raise
    'User id is not set' when the paused vertex re-runs.
    """
    store = InMemoryCheckpointStore()
    first = _graph(store)
    with pytest.raises(GraphPausedException):
        await first.process(fallback_to_env_vars=False)

    checkpoint = await store.load_by_run_id("job-1")
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=store)
    resumed.human_input_decisions = {"pauser:job-1": {"action_id": "approve", "values": {}}}
    paused = resumed.get_vertex("pauser")
    paused.built = False
    paused.custom_component._user_id = None  # restored component starts without a user
    resumed.user_id = "user-123"

    await resumed.process(fallback_to_env_vars=False)

    assert paused.custom_component._user_id == "user-123"
    assert resumed.get_vertex("chat_output").built is True
