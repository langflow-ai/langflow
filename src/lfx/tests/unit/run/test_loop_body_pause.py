"""A Human Input or an asking Agent in a Loop body refuses, instead of running its branch undecided.

Nothing suspends a loop iteration, so a decision requested there used to be dropped and every step
after it ran with no decision. Real graphs, driven by the CLI HITL driver over a SQLite store.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lfx.exceptions.component import ComponentBuildError
from lfx.graph.checkpoint.store import set_default_checkpoint_store
from lfx.run.hitl import LOOP_BODY_HITL_UNSUPPORTED, NestedHITLUnsupportedError, run_graph_with_human_input
from lfx.services.deps import get_settings_service
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore

sys.path.insert(0, str(Path(__file__).parent))
from _pause_flows import graph_from, loop_body_payload, wrapper_payload, write_flow


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


async def _refusal(graph, store) -> tuple[ComponentBuildError, list[dict]]:
    requests: list[dict] = []

    def provider(request: dict) -> dict:
        requests.append(request)
        return {"action_id": "approve", "values": {}}

    graph.user_id, graph.session_id, graph.job_id = "u1", "sess", "job-1"
    graph.set_run_id("job-1")
    with pytest.raises(ComponentBuildError) as caught:
        await run_graph_with_human_input(graph, decision_provider=provider, store=store, input_value="hello")
    return caught.value, requests


@pytest.mark.parametrize("step", ["human_input", "agent"])
async def test_a_decision_in_a_loop_body_refuses_before_any_later_step_runs(step, tmp_path, store):
    marker = tmp_path / "marker.txt"
    marker.write_text("")

    error, requests = await _refusal(graph_from(loop_body_payload(step, marker)), store)

    assert LOOP_BODY_HITL_UNSUPPORTED in str(error)
    assert requests == []
    assert marker.read_text() == ""


@pytest.mark.parametrize("step", ["human_input", "agent"])
async def test_a_decision_in_a_loop_body_of_a_nested_flow_refuses(step, tmp_path, store):
    marker = tmp_path / "marker.txt"
    marker.write_text("")
    write_flow(tmp_path, "child", loop_body_payload(step, marker))

    error, requests = await _refusal(graph_from(wrapper_payload("child", tmp_path)), store)

    assert isinstance(error.__cause__, NestedHITLUnsupportedError)
    assert requests == []
    assert marker.read_text() == ""
