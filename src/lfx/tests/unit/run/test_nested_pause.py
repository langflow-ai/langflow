"""A Run Flow whose child holds a Human Input or an asking Agent pauses the parent and resumes the child.

Real graphs driven by the CLI HITL driver over a SQLite store, so the parent checkpoint goes through
JSON between the pause and the resume. The child's checkpoint rides inside the parent's, and the
decision for the nested request reaches the child at every depth.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.exceptions.component import ComponentBuildError
from lfx.graph import Graph
from lfx.graph.checkpoint.nested import run_nested
from lfx.graph.checkpoint.store import set_default_checkpoint_store
from lfx.helpers.flow import run_flow
from lfx.projects.runtime_artifacts import build_candidate
from lfx.run.hitl import (
    NESTED_HITL_UNSUPPORTED,
    NestedHITLUnsupportedError,
    nested_request_prefix,
    run_graph_with_human_input,
)
from lfx.services.deps import get_settings_service
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore

sys.path.insert(0, str(Path(__file__).parent))
from _pause_flows import (
    CHILD_ID,
    CallerState,
    NestedRunFlow,
    StatefulRunFlow,
    agent_payload,
    candidate_runner_node,
    edge,
    graph_from,
    hitl_payload,
    node,
    parent_graph,
    payload,
    tool_payload,
    wrapper_payload,
    write_flow,
)

PREFIX = nested_request_prefix("runner", "job-1")


@pytest.fixture(autouse=True)
def _allow_test_components(monkeypatch):
    # The stand-in Run Flow builds its child from test-defined components.
    monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)


@pytest.fixture
def store(tmp_path):
    """A durable store for graph checkpoints and, as the default store, for Agent approval state."""
    store = SqliteCheckpointStore(tmp_path / "checkpoints.sqlite")
    set_default_checkpoint_store(store)
    yield store
    set_default_checkpoint_store(None)


def _job(graph: Graph) -> Graph:
    graph.user_id = "u1"
    graph.session_id = "sess"
    graph.job_id = "job-1"
    graph.set_run_id("job-1")
    return graph


async def _drive(graph: Graph, store, action_id: str = "approve", on_pause=None):
    """Run to completion, deciding ``action_id`` at every pause. Returns (requests, {vertex id: outputs})."""
    requests: list[dict] = []

    async def provider(request: dict) -> dict:
        requests.append(request)
        if on_pause is not None:
            await on_pause(request)
        return {"action_id": action_id, "values": {}}

    results = await run_graph_with_human_input(
        _job(graph), decision_provider=provider, store=store, input_value="hello"
    )
    return requests, {r.vertex.id: r.vertex.built_object for r in results}


@pytest.mark.parametrize("levels", [1, 2])
@pytest.mark.parametrize("action_id", ["approve", "reject"])
async def test_nested_human_input_pauses_once_and_the_decision_reaches_the_child(levels, action_id, tmp_path, store):
    requests, outputs = await _drive(parent_graph(tmp_path, levels), store, action_id)

    (request,) = requests
    assert request["request_id"].startswith(PREFIX)
    assert request["request_id"].count(":nested:") == levels
    assert outputs["w_out"]["message"].get_text() == ("w_out:" * (levels - 1)) + f"out_{action_id}:hello"


async def test_the_child_checkpoint_is_stored_in_the_parent_checkpoint(tmp_path, store):
    slots = []

    async def keep_slot(_request):
        slots.append((await store.load_by_run_id("job-1")).child_checkpoints)

    await _drive(parent_graph(tmp_path, 2), store, on_pause=keep_slot)

    (slot,) = slots
    assert list(slot) == [PREFIX]
    # The grandchild's checkpoint nests inside the child's, under the child's run id.
    child = slot[PREFIX]
    assert list(child.child_checkpoints) == [nested_request_prefix("runner", child.run_id)]


async def test_a_finished_child_leaves_no_slot_in_a_later_checkpoint(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload())
    runner = NestedRunFlow(_id="runner", flow_name_selected="child", flow_id_selected=CHILD_ID, flows_dir=str(tmp_path))
    flow = payload(
        [
            node(ChatInput(_id="w_in", should_store_message=False)),
            node(runner),
            node(HumanInput(_id="w_hitl")),
            node(ChatOutput(_id="w_out", should_store_message=False)),
        ],
        [
            edge("w_in", "runner", "message"),
            edge("runner", "w_hitl", "text", field="prompt"),
            edge("w_hitl", "w_out", "branch_approve"),
        ],
    )
    slots = []

    async def keep_slots(_request):
        slots.append(list((await store.load_by_run_id("job-1")).child_checkpoints))

    requests, _ = await _drive(graph_from(flow), store, on_pause=keep_slots)

    # The child's pause, then the parent's own Human Input once the child finished.
    assert len(requests) == 2
    assert slots == [[PREFIX], []]


async def test_a_child_output_built_before_the_pause_reaches_the_parent(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload(early=True))

    _, outputs = await _drive(graph_from(wrapper_payload("child", tmp_path)), store)

    assert sorted(outputs["w_out"]["message"].get_text().split("|")) == ["out_approve:hello", "out_early:hello"]


async def test_a_parent_that_cannot_pause_still_refuses_a_pausing_child(tmp_path):
    parent = _job(parent_graph(tmp_path, 1))
    assert not parent.checkpointing_enabled
    runner = parent.get_vertex("runner").custom_component
    child = Graph.from_payload(hitl_payload(), flow_id=CHILD_ID)

    with pytest.raises(NestedHITLUnsupportedError, match="parent flow"):
        await run_nested(runner, child, lambda: run_flow(inputs={"input_value": "hi"}, user_id="u1", graph=child))


async def test_run_flow_called_as_a_tool_refuses_a_child_that_needs_a_decision(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload())

    requests, outputs = await _drive(graph_from(tool_payload("child", tmp_path)), store)

    # An Agent tool call cannot pause, so the Agent gets the refusal instead of an empty result.
    assert requests == []
    assert NESTED_HITL_UNSUPPORTED in outputs["w_out"]["message"].get_text()


async def test_a_pause_in_the_parents_last_layer_pauses(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload())

    requests, outputs = await _drive(graph_from(wrapper_payload("child", tmp_path, terminal=True)), store)

    assert len(requests) == 1
    assert outputs["runner"]["text"].get_text() == "out_approve:hello"


async def test_a_pause_in_the_childs_last_layer_pauses(tmp_path, store):
    write_flow(tmp_path, "child", agent_payload(terminal=True))

    requests, _ = await _drive(graph_from(wrapper_payload("child", tmp_path)), store)

    # The child Agent is not an output vertex, so its answer does not reach the parent's output.
    assert [request["kind"] for request in requests] == ["tool_approval"]


async def test_a_child_inside_a_harness_candidate_refuses_before_it_runs(store):
    child_id, root_id = str(uuid4()), str(uuid4())
    candidate = build_candidate(
        root_id,
        [
            {"id": root_id, "name": "root", "data": payload([candidate_runner_node(child_id)], [])},
            {"id": child_id, "name": "child", "data": hitl_payload()},
        ],
    )
    graph = Graph.from_payload(candidate.definitions[root_id]["data"], flow_id=root_id, user_id="u1")
    candidate.bind(graph)
    graph.prepare()

    # Restore cannot look the child up in the candidate's definitions yet, so it must not pause.
    with pytest.raises(ComponentBuildError) as caught:
        await _drive(graph, store)
    assert isinstance(caught.value.__cause__, NestedHITLUnsupportedError)


@pytest.mark.parametrize("action_id", ["approve", "reject"])
async def test_nested_pause_keeps_a_child_agent_approval_state(action_id, tmp_path, store):
    write_flow(tmp_path, "child", agent_payload())
    child_run_ids = []

    async def keep_child_run_id(_request):
        child_run_ids.append((await store.load_by_run_id("job-1")).child_checkpoints[PREFIX].run_id)

    requests, outputs = await _drive(
        graph_from(wrapper_payload("child", tmp_path)), store, action_id, on_pause=keep_child_run_id
    )

    (request,) = requests
    assert request["kind"] == "tool_approval"
    text = outputs["w_out"]["message"].get_text()
    # The resumed Agent read its saved approval: it ran the tool only when approved, and never restarted.
    assert text.startswith("c_out:done:")
    assert ("effect" in text) is (action_id == "approve")
    # The state belongs to the parent's job, apart from a parent Agent's state in the same job.
    (child_run_id,) = child_run_ids
    assert await store.load_blob("job-1", f"agent:{child_run_id}:agent") is not None
    assert await store.load_blob(child_run_id, f"agent:{child_run_id}:agent") is None


async def test_a_resumed_child_keeps_the_state_its_caller_attached(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload(approved=CallerState(_id="state")))

    _, outputs = await _drive(graph_from(wrapper_payload("child", tmp_path, runner=StatefulRunFlow)), store)

    # CallerState runs only after the decision, so it reads the restored child.
    assert outputs["w_out"]["message"].get_text() == f"out_approve:run-flow|['{CHILD_ID}']|['extra-scope']|child"


async def test_a_child_changed_while_paused_refuses_to_resume(tmp_path, store):
    write_flow(tmp_path, "child", hitl_payload())

    async def edit_child(_request):
        write_flow(tmp_path, "child", hitl_payload(early=True))

    with pytest.raises(ComponentBuildError, match="changed while this run waited for a decision"):
        await _drive(graph_from(wrapper_payload("child", tmp_path)), store, on_pause=edit_child)


def _two_pauses_in_one_layer(flows_dir: Path) -> dict:
    """Chat Input -> two Run Flows side by side, each running the Human Input flow."""
    write_flow(flows_dir, "level0", hitl_payload())
    runners = [
        NestedRunFlow(
            _id=f"runner_{n}", flow_name_selected="level0", flow_id_selected=CHILD_ID, flows_dir=str(flows_dir)
        )
        for n in ("a", "b")
    ]
    return payload(
        [node(ChatInput(_id="w_in", should_store_message=False)), *(node(r) for r in runners)],
        [edge("w_in", r._id, "message") for r in runners],
    )


def _two_human_inputs_in_one_layer() -> dict:
    nodes = [node(ChatInput(_id="c_in", should_store_message=False))]
    edges = []
    for name in ("a", "b"):
        nodes += [node(HumanInput(_id=f"hitl_{name}")), node(ChatOutput(_id=f"out_{name}", should_store_message=False))]
        edges += [
            edge("c_in", f"hitl_{name}", "message", field="prompt"),
            edge(f"hitl_{name}", f"out_{name}", "branch_approve"),
        ]
    return payload(nodes, edges)


async def test_two_pauses_in_one_layer_fail_instead_of_dropping_a_decision(tmp_path, store):
    with pytest.raises(ComponentBuildError, match="asked for a decision at the same time"):
        await _drive(graph_from(_two_pauses_in_one_layer(tmp_path)), store)


async def test_two_pauses_in_one_layer_of_the_child_reach_the_parent_as_a_conflict(tmp_path, store):
    write_flow(tmp_path, "child", _two_human_inputs_in_one_layer())

    with pytest.raises(ComponentBuildError, match="asked for a decision at the same time"):
        await _drive(graph_from(wrapper_payload("child", tmp_path)), store)
