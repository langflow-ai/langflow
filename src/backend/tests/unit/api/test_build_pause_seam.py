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

import pytest
from fastapi import BackgroundTasks
from langflow.api.build import generate_flow_events
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.exceptions import GraphPausedException
from lfx.schema.schema import InputValueRequest

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


async def test_build_path_pause_persists_checkpoint_and_propagates_unwrapped(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    store = InMemoryCheckpointStore()

    async def probe(_job_id: str) -> str:
        return "pause"

    _wrap_graph_config(monkeypatch, store=store, probe=probe)
    queue, error = await _drive_build(flow_id, active_user)

    assert isinstance(error, GraphPausedException), f"expected unwrapped GraphPausedException, got {error!r}"
    checkpoint = await store.load(error.checkpoint_id)
    assert checkpoint is not None
    assert checkpoint.job_id == "job-1"
    events = _drain_events(queue)
    error_events = [e for e in events if e.get("event") == "error"]
    assert not error_events, f"pause must not be terminalized as an error event: {error_events}"


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
