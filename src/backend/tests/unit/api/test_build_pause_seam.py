"""LE-1440 S4: build-path pause detection seam + propagate-unwrapped guard.

Drives the REAL background build loop (generate_flow_events → build_vertices →
_build_vertex) against a real DB flow and real services. The only injection is
a thin wrapper around build_graph_from_db that flips the checkpointing config
on the real graph — the seam LE-1442 will own in production.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from langflow.api.build import generate_flow_events
from langflow.services.deps import get_settings_service
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.schema.schema import InputValueRequest

from tests.unit.api.v2._scripted_agent import ScriptedAgent
from tests.unit.build_utils import create_flow

if TYPE_CHECKING:
    import uuid

pytestmark = pytest.mark.usefixtures("client")


def _wrap_graph_config(monkeypatch, *, store, probe):
    import langflow.api.build as build_module

    real_build_graph_from_db = build_module.build_graph_from_db

    async def wrapper(**kwargs):
        graph = await real_build_graph_from_db(**kwargs)
        graph.checkpointing_enabled = True
        graph.checkpoint_store = store
        graph.job_id = "job-1"
        graph.pause_probe = probe
        return graph

    monkeypatch.setattr(build_module, "build_graph_from_db", wrapper)


async def _drive_build(flow_id: uuid.UUID, active_user) -> tuple[asyncio.Queue, BaseException | None]:
    queue: asyncio.Queue = asyncio.Queue()
    error: BaseException | None = None
    try:
        await generate_flow_events(
            flow_id=flow_id,
            background_tasks=BackgroundTasks(),
            event_manager=create_default_event_manager(queue),
            inputs=InputValueRequest(session=str(flow_id)),
            data=None,
            files=None,
            stop_component_id=None,
            start_component_id=None,
            log_builds=False,
            current_user=active_user,
            expose_error_details=False,
        )
    except BaseException as exc:
        error = exc
    return queue, error


def _drain_events(queue: asyncio.Queue) -> list[dict]:
    events = []
    while not queue.empty():
        item = queue.get_nowait()
        payload = item[1]
        if payload is None:
            continue
        events.append(json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload))
    return events


async def test_build_path_pause_persists_checkpoint_and_emits_human_input_required(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    store = InMemoryCheckpointStore()

    async def probe(_job_id: str) -> str:
        return "pause"

    _wrap_graph_config(monkeypatch, store=store, probe=probe)
    queue, error = await _drive_build(flow_id, active_user)

    # The build/SSE seam catches the pause and surfaces it as a human_input_required event (the HITL
    # card) — it must NOT escape as an exception or be terminalized as an error event. The unwrapped
    # propagation guard lives one layer down (Graph._run / execute_with_status), not here.
    assert error is None, f"pause must be caught at the build seam, got {error!r}"
    events = _drain_events(queue)
    assert any(e.get("event") == "human_input_required" for e in events), (
        f"expected a human_input_required event, got {[e.get('event') for e in events]}"
    )
    assert not [e for e in events if e.get("event") == "error"], "pause must not emit an error event"

    # The durable checkpoint was persisted (keyed by job_id) so a later resume can restore it.
    persisted = [cp for cp in store._checkpoints.values() if cp.job_id == "job-1"]
    assert persisted, "expected a persisted checkpoint for job-1"


async def test_build_path_noop_probe_completes(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    store = InMemoryCheckpointStore()

    async def probe(_job_id: str) -> str:
        return "run"

    _wrap_graph_config(monkeypatch, store=store, probe=probe)
    queue, error = await _drive_build(flow_id, active_user)

    assert error is None, f"no-op probe must complete the build, got {error!r}"
    events = _drain_events(queue)
    assert any(e.get("event") == "end" for e in events)


async def test_build_path_cancel_decision_propagates_cancelled_error(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)

    async def probe(_job_id: str) -> str:
        return "cancel"

    _wrap_graph_config(monkeypatch, store=InMemoryCheckpointStore(), probe=probe)
    queue, error = await _drive_build(flow_id, active_user)

    assert isinstance(error, asyncio.CancelledError), f"expected unwrapped CancelledError, got {error!r}"
    events = _drain_events(queue)
    error_events = [e for e in events if e.get("event") == "error"]
    assert not error_events


async def test_build_path_pauses_when_the_last_vertex_asks_for_a_decision(
    client, logged_in_headers, active_user, monkeypatch
):
    # The Agent's model and tool are scripted in its own code, which makes it a custom component.
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "custom_component_admin_only", False)
    response = await client.get("api/v1/all", headers=logged_in_headers)
    chat_input = next(category["ChatInput"] for category in response.json().values() if "ChatInput" in category)
    agent = ScriptedAgent(_id="Agent", tool_policy="ask").to_frontend_node()["data"]["node"]
    source = {"dataType": "ChatInput", "id": "In", "name": "message", "output_types": ["Message"]}
    target = {"fieldName": "input_value", "id": "Agent", "inputTypes": ["Message"], "type": "str"}
    # Chat Input -> the Agent, which is the last vertex: no later vertex build checks for its pause.
    flow = {
        "name": f"last-layer-{uuid4()}",
        "data": {
            "nodes": [
                {"id": node_id, "type": "genericNode", "position": {"x": 0, "y": 0}, "data": data}
                for node_id, data in (
                    ("In", {"id": "In", "type": "ChatInput", "node": chat_input}),
                    ("Agent", {"id": "Agent", "type": "ScriptedAgent", "node": agent}),
                )
            ],
            "edges": [
                {
                    "id": "In-Agent",
                    "source": "In",
                    "target": "Agent",
                    "data": {"sourceHandle": source, "targetHandle": target},
                }
            ],
        },
    }
    flow_id = await create_flow(client, json.dumps(flow), logged_in_headers)
    store = InMemoryCheckpointStore()

    async def probe(_job_id: str) -> str:
        return "run"

    _wrap_graph_config(monkeypatch, store=store, probe=probe)
    queue, error = await _drive_build(flow_id, active_user)

    assert error is None, f"pause must be caught at the build seam, got {error!r}"
    pauses = [e["data"] for e in _drain_events(queue) if e.get("event") == "human_input_required"]
    assert [pause["kind"] for pause in pauses] == ["tool_approval"]
    assert [cp.job_id for cp in store._checkpoints.values()] == ["job-1"]
