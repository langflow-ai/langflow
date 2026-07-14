"""CLI HITL driver (``run_graph_with_human_input``).

A real ChatInput -> StaticPauser -> ChatOutput graph driven through one or more
pauses by a scripted decision provider, proving the driver loops process() +
restore + inject + un-build until the run completes and returns per-vertex results
in the same shape ``async_start`` yields (so the CLI output extractors work).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.run.hitl import run_graph_with_human_input

sys.path.insert(0, str(Path(__file__).parent.parent / "graph" / "checkpoint"))
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


async def test_driver_resolves_a_pause_and_completes() -> None:
    store = InMemoryCheckpointStore()
    graph = _graph(store)
    seen: list[dict] = []

    def provider(request: dict) -> dict:
        seen.append(request)
        return {"action_id": "approve", "values": {}}

    results = await run_graph_with_human_input(graph, decision_provider=provider, store=store)

    assert len(seen) == 1
    assert seen[0]["request_id"] == "pauser:job-1"
    chat_outputs = [r for r in results if r.vertex.id == "chat_output"]
    assert chat_outputs
    assert chat_outputs[0].vertex.built


async def test_driver_supports_an_async_decision_provider() -> None:
    store = InMemoryCheckpointStore()
    graph = _graph(store)

    async def provider(_request: dict) -> dict:
        return {"action_id": "approve", "values": {}}

    results = await run_graph_with_human_input(graph, decision_provider=provider, store=store)

    assert any(r.vertex.id == "chat_output" for r in results)


async def test_driver_injects_the_chosen_decision_downstream() -> None:
    from lfx.cli.script_loader import extract_text_from_result

    store = InMemoryCheckpointStore()
    graph = _graph(store)

    results = await run_graph_with_human_input(
        graph,
        decision_provider=lambda _r: {"action_id": "reject", "values": {}},
        store=store,
    )

    # The injected decision flows through the pauser to the Chat Output the CLI prints.
    assert extract_text_from_result(results) == "reject"


async def test_driver_runs_a_non_pausing_graph_straight_through() -> None:
    store = InMemoryCheckpointStore()
    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.set_run_id("job-2")

    called = False

    def provider(_request: dict) -> dict:
        nonlocal called
        called = True
        return {}

    results = await run_graph_with_human_input(graph, decision_provider=provider, store=store)

    assert called is False
    assert any(r.vertex.id == "chat_output" for r in results)


def test_flow_has_pausing_node_detects_human_input() -> None:
    from types import SimpleNamespace

    from lfx.run.hitl import flow_has_pausing_node

    with_pauser = SimpleNamespace(
        vertices=[SimpleNamespace(data={"type": "ChatInput"}), SimpleNamespace(data={"type": "HumanInput"})]
    )
    without = SimpleNamespace(vertices=[SimpleNamespace(data={"type": "ChatInput"})])

    assert flow_has_pausing_node(with_pauser) is True
    assert flow_has_pausing_node(without) is False


def test_terminal_decision_provider_reads_the_chosen_option(monkeypatch) -> None:
    import io

    from lfx.run.hitl import terminal_decision_provider

    request = {"prompt": "Approve?", "options": [{"action_id": "approve"}, {"action_id": "reject"}]}

    monkeypatch.setattr("sys.stdin", io.StringIO("2\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    assert terminal_decision_provider(request) == {"action_id": "reject", "values": {}}

    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    assert terminal_decision_provider(request) == {"action_id": "approve", "values": {}}


async def test_driver_raises_when_provider_never_resolves() -> None:
    store = InMemoryCheckpointStore()
    graph = _graph(store)

    from lfx.graph.exceptions import GraphPausedException

    # A provider that never supplies a decision (returns None) re-pauses forever;
    # the driver's _MAX_PAUSES guard must surface the pause rather than loop.
    with pytest.raises(GraphPausedException):
        await run_graph_with_human_input(graph, decision_provider=lambda _r: None, store=store)


def _hitl_graph(store, *, enable_fallback: bool, late: bool, job_id: str = "job-1"):
    """A real HumanInput node wired to two branch outputs (approve + fallback).

    ``late=True`` backdates the pause so the driver sees the response as past-deadline.
    HumanInput's branch outputs are dynamic, so they're materialized + wired by name here.
    """
    from datetime import datetime, timedelta, timezone

    from lfx.components.flow_controls.human_input import HumanInput
    from lfx.io import Output

    human = HumanInput(_id="human")
    human.set(
        prompt="Approve?",
        decisions=["Approve"],
        enable_fallback=enable_fallback,
        timeout={"value": 1, "unit": "Minutes"},
    )
    if late:
        original = human._pause_request

        def _backdated():
            req = original()
            req["paused_at"] = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
            return req

        human._pause_request = _backdated
    human.outputs = [
        Output(
            display_name="Approve", name="branch_approve", method="route_branch", group_outputs=True, types=["Message"]
        ),
        Output(
            display_name="Fallback",
            name="branch_fallback",
            method="route_branch",
            group_outputs=True,
            types=["Message"],
        ),
    ]
    human.map_outputs()
    out_approve = ChatOutput(_id="out_approve")
    out_approve.set(should_store_message=False)
    out_fallback = ChatOutput(_id="out_fallback")
    out_fallback.set(should_store_message=False)
    graph = Graph()
    graph.add_component(human, "human")
    graph.add_component(out_approve, "out_approve")
    graph.add_component(out_fallback, "out_fallback")
    graph.add_component_edge("human", ("branch_approve", "input_value"), "out_approve")
    graph.add_component_edge("human", ("branch_fallback", "input_value"), "out_fallback")
    graph.set_run_id(job_id)
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    return graph


async def test_late_decision_routes_to_fallback_branch() -> None:
    store = InMemoryCheckpointStore()
    graph = _hitl_graph(store, enable_fallback=True, late=True)
    results = await run_graph_with_human_input(
        graph, decision_provider=lambda _r: {"action_id": "approve", "values": {}}, store=store
    )
    built = {r.vertex.id for r in results}
    assert "out_fallback" in built
    assert "out_approve" not in built


async def test_ontime_decision_routes_to_chosen_branch() -> None:
    store = InMemoryCheckpointStore()
    graph = _hitl_graph(store, enable_fallback=True, late=False)
    results = await run_graph_with_human_input(
        graph, decision_provider=lambda _r: {"action_id": "approve", "values": {}}, store=store
    )
    built = {r.vertex.id for r in results}
    assert "out_approve" in built
    assert "out_fallback" not in built


def _two_hitl_graph(store, *, job_id="job-1"):
    """Two HumanInput nodes in sequence (human1 -> human2 -> final_out), both approve-only.

    Reproduces the multi-HITL resume loop: approving human2 must not re-pause human1.
    """
    from lfx.components.flow_controls.human_input import HumanInput
    from lfx.io import Output

    def _approve_only(_id):
        human = HumanInput(_id=_id)
        human.set(prompt="Approve?", decisions=["Approve"], enable_fallback=False)
        human.outputs = [
            Output(
                display_name="Approve",
                name="branch_approve",
                method="route_branch",
                group_outputs=True,
                types=["Message"],
            )
        ]
        human.map_outputs()
        return human

    human1 = _approve_only("human1")
    human2 = _approve_only("human2")
    final_out = ChatOutput(_id="final_out")
    final_out.set(should_store_message=False)
    graph = Graph()
    graph.add_component(human1, "human1")
    graph.add_component(human2, "human2")
    graph.add_component(final_out, "final_out")
    graph.add_component_edge("human1", ("branch_approve", "prompt"), "human2")
    graph.add_component_edge("human2", ("branch_approve", "input_value"), "final_out")
    graph.set_run_id(job_id)
    graph.checkpointing_enabled = True
    graph.checkpoint_store = store
    return graph


async def test_two_sequential_hitl_nodes_finish_without_relooping() -> None:
    store = InMemoryCheckpointStore()
    graph = _two_hitl_graph(store)
    asked: list[str] = []

    def provider(request: dict) -> dict:
        asked.append(request["request_id"])
        return {"action_id": "approve", "values": {}}

    results = await run_graph_with_human_input(graph, decision_provider=provider, store=store)

    built = {r.vertex.id for r in results}
    assert "final_out" in built  # the run finalizes after the last HITL
    # Each HITL is asked exactly once: approving human2 must NOT re-pause human1 (no ping-pong loop).
    assert asked == ["human1:job-1", "human2:job-1"]
