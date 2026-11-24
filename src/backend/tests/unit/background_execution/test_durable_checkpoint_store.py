"""Durable checkpoint persistence (LE-1441) against REAL SQLite and REAL Postgres.

Slice 1 — the encoding-agnostic ``JobService`` checkpoint helper. The blob is
already-serialized text the helper never parses, so a graph-kind (JSON) and an
agent-kind (base64) payload both round-trip byte-for-byte through the same API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.graph.checkpoint.store import CheckpointStore


def _checkpoint(job_id, *, run_id=None, session_id="sess-1", **overrides) -> GraphCheckpoint:
    base = {
        "run_id": run_id or str(job_id),
        "flow_id": "flow-1",
        "session_id": session_id,
        "job_id": str(job_id),
        "flow_payload": {"nodes": [], "edges": []},
        "vertices_to_run": {"a", "b"},
        "ran_at_least_once": {"a"},
    }
    base.update(overrides)
    return GraphCheckpoint(**base)


async def _new_job(service):
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    return job_id


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_save_and_load_checkpoint_round_trips_opaque_blob(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    blob = '{"checkpoint_id": "abc", "run_id": "r1"}'
    await service.save_checkpoint(job_id, "graph", blob)

    assert await service.load_checkpoint(job_id, "graph") == blob


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_load_checkpoint_returns_none_when_absent(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    assert await service.load_checkpoint(job_id, "graph") is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_save_checkpoint_upserts_single_row_per_kind(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await service.save_checkpoint(job_id, "graph", "first")
    await service.save_checkpoint(job_id, "graph", "second")

    assert await service.load_checkpoint(job_id, "graph") == "second"


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_concurrent_first_save_does_not_raise_integrity_error(real_services_job_service) -> None:
    """Racing savers of the first checkpoint must not hit UNIQUE — the loser retries into update."""
    import asyncio

    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await asyncio.gather(*[service.save_checkpoint(job_id, "graph", f"blob-{i}") for i in range(8)])

    assert (await service.load_checkpoint(job_id, "graph")).startswith("blob-")


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_kinds_are_isolated_per_job(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    graph_blob = '{"kind": "graph"}'
    agent_blob = "gqFhAaFiAg=="  # stand-in for base64(msgpack) — raw bytes can't sit in JSON

    await service.save_checkpoint(job_id, "graph", graph_blob)
    await service.save_checkpoint(job_id, "agent", agent_blob)

    assert await service.load_checkpoint(job_id, "graph") == graph_blob
    assert await service.load_checkpoint(job_id, "agent") == agent_blob


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_delete_checkpoint_removes_row(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await service.save_checkpoint(job_id, "graph", "blob")
    await service.delete_checkpoint(job_id, "graph")

    assert await service.load_checkpoint(job_id, "graph") is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_delete_checkpoint_is_noop_when_absent(real_services_job_service) -> None:
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())

    await service.delete_checkpoint(job_id, "graph")  # must not raise

    assert await service.load_checkpoint(job_id, "graph") is None


def _store(job_service):
    from langflow.services.checkpoint.store import JobScopedCheckpointStore

    return JobScopedCheckpointStore(job_service)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
def test_durable_store_is_a_checkpoint_store() -> None:
    from langflow.services.checkpoint.store import JobScopedCheckpointStore

    assert issubclass(JobScopedCheckpointStore, CheckpointStore)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_save_then_load_by_run_id_returns_same_checkpoint(real_services_job_service) -> None:
    store = _store(real_services_job_service)
    job_id = await _new_job(real_services_job_service)
    cp = _checkpoint(job_id)

    await store.save(cp)
    loaded = await store.load_by_run_id(str(job_id))

    assert loaded is not None
    assert loaded.checkpoint_id == cp.checkpoint_id
    assert loaded.run_id == cp.run_id
    assert loaded.vertices_to_run == {"a", "b"}  # set field survives JSON round-trip
    assert loaded.ran_at_least_once == {"a"}


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_scan_based_lookups_raise_not_implemented(real_services_job_service) -> None:
    # The durable store is job-scoped; load/delete by checkpoint id and list_by_session would scan
    # across all jobs/users. They fail loud so a future caller can't trigger a silent cross-user scan.
    store = _store(real_services_job_service)
    with pytest.raises(NotImplementedError):
        await store.load("any-checkpoint-id")
    with pytest.raises(NotImplementedError):
        await store.delete("any-checkpoint-id")
    with pytest.raises(NotImplementedError):
        await store.list_by_session("any-session")


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_load_by_run_id_returns_latest_save(real_services_job_service) -> None:
    store = _store(real_services_job_service)
    job_id = await _new_job(real_services_job_service)
    first = _checkpoint(job_id, call_order=["v1"])
    second = _checkpoint(job_id, call_order=["v1", "v2"])

    await store.save(first)
    await store.save(second)

    loaded = await store.load_by_run_id(str(job_id))
    assert loaded is not None
    assert loaded.call_order == ["v1", "v2"]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_load_by_run_id_missing_returns_none(real_services_job_service) -> None:
    store = _store(real_services_job_service)
    assert await store.load_by_run_id("ghost") is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_load_by_run_id_honors_expiry(real_services_job_service) -> None:
    store = _store(real_services_job_service)
    job_id = await _new_job(real_services_job_service)
    cp = _checkpoint(job_id, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))

    await store.save(cp)

    assert await store.load_by_run_id(str(job_id)) is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_checkpoint_survives_a_fresh_store_on_same_db(real_services_job_service) -> None:
    """A second store + JobService on the SAME DB returns the saved checkpoint field-for-field."""
    from langflow.services.jobs.service import JobService

    store_1 = _store(real_services_job_service)
    job_id = await _new_job(real_services_job_service)
    cp = _checkpoint(job_id, run_map={"a": ["b"]})
    await store_1.save(cp)

    store_2 = _store(JobService())
    loaded = await store_2.load_by_run_id(str(job_id))

    assert loaded is not None
    assert loaded.checkpoint_id == cp.checkpoint_id
    assert loaded.run_map == {"a": ["b"]}
    assert loaded.vertices_to_run == {"a", "b"}


@pytest.mark.no_blockbuster
def test_checkpoint_factory_registers_durable_store() -> None:
    """In-app, the registered CHECKPOINT_SERVICE resolves to the durable store."""
    from langflow.services.checkpoint.factory import CheckpointServiceFactory
    from langflow.services.checkpoint.store import JobScopedCheckpointStore
    from lfx.services.deps import get_checkpoint_service
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    manager = get_service_manager()
    saved = manager.services.pop(ServiceType.CHECKPOINT_SERVICE, None)
    try:
        manager.register_factory(CheckpointServiceFactory())
        resolved = get_checkpoint_service()
        assert isinstance(resolved, JobScopedCheckpointStore)
    finally:
        manager.services.pop(ServiceType.CHECKPOINT_SERVICE, None)
        if saved is not None:
            manager.services[ServiceType.CHECKPOINT_SERVICE] = saved


@pytest.mark.no_blockbuster
def test_standalone_checkpoint_service_is_in_memory() -> None:
    """With no registered service, the lfx accessor falls back to the in-memory store."""
    from lfx.graph.checkpoint.store import InMemoryCheckpointStore
    from lfx.services.deps import get_checkpoint_service
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    manager = get_service_manager()
    saved = manager.services.pop(ServiceType.CHECKPOINT_SERVICE, None)
    saved_factory = manager.factories.pop(ServiceType.CHECKPOINT_SERVICE, None)
    try:
        assert isinstance(get_checkpoint_service(), InMemoryCheckpointStore)
    finally:
        if saved is not None:
            manager.services[ServiceType.CHECKPOINT_SERVICE] = saved
        if saved_factory is not None:
            manager.factories[ServiceType.CHECKPOINT_SERVICE] = saved_factory


def _runnable_graph(job_id, *, store=None, probe=None):
    """Real ChatInput→ChatOutput graph; run_id carries the job_id so resume resolves it."""
    from lfx.components.input_output import ChatInput, ChatOutput
    from lfx.graph import Graph

    chat_input = ChatInput(_id="chat_input", input_value="hello")
    chat_input.set(should_store_message=False)
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response, should_store_message=False)
    graph = Graph(chat_input, chat_output)
    graph.session_id = "sess-1"
    graph.set_run_id(str(job_id))
    graph.job_id = str(job_id)
    if store is not None:
        graph.checkpointing_enabled = True
        graph.checkpoint_store = store
    if probe is not None:
        graph.pause_probe = probe
    return graph


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_e2e_save_restart_resume_matches_never_paused_control(real_services_job_service) -> None:
    from langflow.services.jobs.service import JobService
    from lfx.graph import Graph
    from lfx.graph.exceptions import GraphPausedException

    control = _runnable_graph(uuid4())
    await control.process(fallback_to_env_vars=False)
    control_text = control.get_vertex("chat_output").results["message"].text

    job_id = await _new_job(real_services_job_service)
    durable = _store(real_services_job_service)
    calls = {"n": 0}

    async def probe(_job_id: str) -> str:
        calls["n"] += 1
        return "run" if calls["n"] == 1 else "pause"  # build chat_input, then pause before chat_output

    paused = _runnable_graph(job_id, store=durable, probe=probe)
    with pytest.raises(GraphPausedException):
        await paused.process(fallback_to_env_vars=False)
    assert paused.get_vertex("chat_input").built is True
    assert paused.get_vertex("chat_output").built is False

    # Restart: a fresh store + JobService on the SAME DB, no shared in-process state.
    fresh = _store(JobService())
    checkpoint = await fresh.load_by_run_id(str(job_id))
    assert checkpoint is not None

    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=fresh)
    assert resumed.get_vertex("chat_input").built is True
    # The already-built input is not re-queued: only the remaining layer runs.
    assert resumed.resume_first_layer() == ["chat_output"]

    await resumed.process(fallback_to_env_vars=False)

    output_vertex = resumed.get_vertex("chat_output")
    assert output_vertex.built is True
    assert output_vertex.results["message"].text == control_text
