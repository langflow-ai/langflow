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
