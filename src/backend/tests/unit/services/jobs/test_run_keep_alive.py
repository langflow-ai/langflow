"""Runs that execute in their own request must stay live for as long as they run.

v1 /run, v2 sync workflows, playground builds and memory-base ingestion mark
their job IN_PROGRESS through ``execute_with_status``, outside the background
runner, which heartbeats only its own jobs. A job with no heartbeat looks
orphaned to the first sweep that runs while it is in flight (the Redis-fallback
watchdog, or a sibling worker's startup sweep), which fails it as worker_lost.
The run still ends COMPLETED, but the worker_lost error and its run_failed
event stay on the job.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest
from fastapi import BackgroundTasks
from langflow.api.build import generate_flow_events
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.memory_base.model import MemoryBase, MemoryBaseSession
from langflow.services.deps import get_job_service, get_settings_service
from lfx.events.event_manager import create_default_event_manager
from lfx.graph.exceptions import GraphPausedException
from lfx.schema.schema import InputValueRequest

from tests.unit.build_utils import create_flow

LEASE_TTL_S = 1.0


class _Gate:
    """Holds a run mid-flight until released."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def hold(self) -> None:
        self.entered.set()
        await self.release.wait()


@pytest.fixture
def fast_heartbeat(client, monkeypatch):  # noqa: ARG001 -- after the app has built its settings service
    monkeypatch.setattr(get_settings_service().settings, "background_heartbeat_interval_s", 0.1)


async def _dead_job(job_service) -> uuid.UUID:
    """A run whose worker died. The sweep that spares the live run must still fail it."""
    job_id = uuid.uuid4()
    await job_service.create_job(job_id=job_id, flow_id=job_id, status=JobStatus.IN_PROGRESS)
    return job_id


async def _sweep_while_held(job_service, gate: _Gate) -> list[uuid.UUID]:
    await asyncio.wait_for(gate.entered.wait(), timeout=10)
    # Outlive the lease and the insert-time heartbeat, so only the run's own
    # keep-alive keeps its job fresh.
    await asyncio.sleep(LEASE_TTL_S * 1.5)
    return await job_service.sweep_orphans(lease_ttl_s=LEASE_TTL_S)


async def _heartbeat_at(job_service, job_id: uuid.UUID) -> str:
    job = await job_service.get_job_by_job_id(job_id)
    return job.job_metadata["heartbeat_at"]


async def _assert_completed_cleanly(job_service, job_id: uuid.UUID) -> None:
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.error is None
    events = await job_service.read_events(job_id)
    assert not [event for event in events if event.event_type == "run_failed"]


@pytest.mark.usefixtures("client", "fast_heartbeat")
@pytest.mark.parametrize("inserted_as", [JobStatus.QUEUED, JobStatus.IN_PROGRESS])
async def test_kept_alive_run_outlives_the_lease(inserted_as):
    job_service = get_job_service()
    dead_job_id = await _dead_job(job_service)
    job_id = uuid.uuid4()
    await job_service.create_job(job_id=job_id, flow_id=job_id, status=inserted_as, heartbeat=True)
    gate = _Gate()

    async def run() -> str:
        await gate.hold()
        return "done"

    task = asyncio.create_task(
        job_service.execute_with_status(job_id, run, mark_in_progress=inserted_as == JobStatus.QUEUED, keep_alive=True)
    )
    try:
        swept = await _sweep_while_held(job_service, gate)
    finally:
        gate.release.set()
        result = await asyncio.wait_for(task, timeout=10)

    assert swept == [dead_job_id]
    assert result == "done"
    await _assert_completed_cleanly(job_service, job_id)


@pytest.mark.usefixtures("client")
async def test_short_kept_alive_run_writes_no_heartbeat():
    """The insert-time heartbeat covers a run shorter than one interval, so it costs no write."""
    job_service = get_job_service()
    job_id = uuid.uuid4()
    await job_service.create_job(job_id=job_id, flow_id=job_id, status=JobStatus.IN_PROGRESS, heartbeat=True)
    inserted_at = await _heartbeat_at(job_service, job_id)

    async def run() -> None:
        await asyncio.sleep(0.05)

    await job_service.execute_with_status(job_id, run, mark_in_progress=False, keep_alive=True)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.job_metadata["heartbeat_at"] == inserted_at


@pytest.mark.usefixtures("client", "fast_heartbeat")
async def test_keep_alive_stops_when_the_run_pauses():
    """A pause leaves the job IN_PROGRESS for its caller, and must not keep it looking live."""
    job_service = get_job_service()
    job_id = uuid.uuid4()
    await job_service.create_job(job_id=job_id, flow_id=job_id, status=JobStatus.IN_PROGRESS, heartbeat=True)
    inserted_at = await _heartbeat_at(job_service, job_id)
    pause = GraphPausedException("checkpoint", "human input")

    async def run() -> None:
        # Pause only once the keep-alive has beaten, so stopping it is what the test sees.
        while await _heartbeat_at(job_service, job_id) == inserted_at:  # noqa: ASYNC110 -- polls a DB row
            await asyncio.sleep(0.05)
        raise pause

    with pytest.raises(GraphPausedException):
        await asyncio.wait_for(
            job_service.execute_with_status(job_id, run, mark_in_progress=False, keep_alive=True), timeout=10
        )
    paused_at = await _heartbeat_at(job_service, job_id)
    await asyncio.sleep(0.5)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS
    assert job.job_metadata["heartbeat_at"] == paused_at


@pytest.mark.usefixtures("client", "fast_heartbeat")
@pytest.mark.parametrize("ending", ["error", "cancel", "cancel_scope"])
async def test_keep_alive_ends_with_the_run(ending):
    """However the run ends, its heartbeat ends with it.

    A cancel scope, as a client disconnect produces, cancels every await in the
    run's cancel handling too, so the terminal write may never land and the row
    stays IN_PROGRESS. A heartbeat that outlived the run would keep it looking
    live for good.
    """
    job_service = get_job_service()
    job_id = uuid.uuid4()
    await job_service.create_job(job_id=job_id, flow_id=job_id, status=JobStatus.IN_PROGRESS, heartbeat=True)
    inserted_at = await _heartbeat_at(job_service, job_id)
    beaten = asyncio.Event()
    failure = RuntimeError("component failed")

    async def run() -> None:
        # End only once the keep-alive has beaten, so stopping it is what the test sees.
        while await _heartbeat_at(job_service, job_id) == inserted_at:  # noqa: ASYNC110 -- polls a DB row
            await asyncio.sleep(0.05)
        beaten.set()
        if ending == "error":
            raise failure
        await asyncio.Event().wait()

    execution = job_service.execute_with_status(job_id, run, mark_in_progress=False, keep_alive=True)
    if ending == "error":
        with pytest.raises(RuntimeError):
            await asyncio.wait_for(execution, timeout=10)
    elif ending == "cancel":
        task = asyncio.create_task(execution)
        await asyncio.wait_for(beaten.wait(), timeout=10)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with anyio.CancelScope(deadline=anyio.current_time() + 10) as scope:

            async def cancel_once_beaten() -> None:
                await beaten.wait()
                scope.cancel()

            canceller = asyncio.create_task(cancel_once_beaten())
            await execution
        await canceller
    assert beaten.is_set()
    # Let a heartbeat write that was already in flight land first.
    await asyncio.sleep(0.2)
    ended_at = await _heartbeat_at(job_service, job_id)
    await asyncio.sleep(0.5)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.job_metadata["heartbeat_at"] == ended_at
    if ending != "cancel_scope":
        assert job.status == JobStatus.FAILED


@pytest.mark.usefixtures("fast_heartbeat")
async def test_v1_run_is_not_swept_while_it_runs(client, simple_api_test, created_api_key, monkeypatch):
    from langflow.api.v1 import endpoints

    job_service = get_job_service()
    dead_job_id = await _dead_job(job_service)
    gate = _Gate()
    run_ids: list[uuid.UUID] = []

    async def held_run(*, graph, flow_id, session_id, **_kwargs):
        run_ids.append(uuid.UUID(graph.run_id))
        await gate.hold()
        return [], session_id or flow_id

    monkeypatch.setattr(endpoints, "run_graph_internal", held_run)
    request = asyncio.create_task(
        client.post(
            f"/api/v1/run/{simple_api_test['id']}",
            headers={"x-api-key": created_api_key.api_key},
            json={"input_value": "hi"},
        )
    )
    try:
        swept = await _sweep_while_held(job_service, gate)
    finally:
        gate.release.set()
        response = await asyncio.wait_for(request, timeout=10)

    assert response.status_code == 200, response.text
    assert swept == [dead_job_id]
    await _assert_completed_cleanly(job_service, run_ids[0])


@pytest.mark.usefixtures("fast_heartbeat")
async def test_v2_sync_workflow_is_not_swept_while_it_runs(client, simple_api_test, created_api_key, monkeypatch):
    from langflow.api.v2 import workflow_execution

    job_service = get_job_service()
    dead_job_id = await _dead_job(job_service)
    gate = _Gate()

    async def held_run(*, flow_id, session_id, **_kwargs):
        await gate.hold()
        return [], session_id or flow_id

    monkeypatch.setattr(workflow_execution, "run_graph_internal", held_run)
    request = asyncio.create_task(
        client.post(
            "api/v2/workflows",
            headers={"x-api-key": created_api_key.api_key},
            json={"flow_id": simple_api_test["id"], "input_value": "hi", "mode": "sync"},
        )
    )
    try:
        swept = await _sweep_while_held(job_service, gate)
    finally:
        gate.release.set()
        response = await asyncio.wait_for(request, timeout=10)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed", response.text
    assert swept == [dead_job_id]
    await _assert_completed_cleanly(job_service, uuid.UUID(response.json()["job_id"]))


@pytest.mark.usefixtures("fast_heartbeat")
async def test_playground_build_is_not_swept_while_it_runs(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user, monkeypatch
):
    import langflow.api.build as build_module

    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    job_service = get_job_service()
    dead_job_id = await _dead_job(job_service)
    gate = _Gate()
    real_build_graph_from_db = build_module.build_graph_from_db

    async def graph_held_before_its_vertices(**kwargs):
        graph = await real_build_graph_from_db(**kwargs)
        check_and_handle_pause = graph.check_and_handle_pause

        async def held_check() -> None:
            await gate.hold()
            await check_and_handle_pause()

        graph.check_and_handle_pause = held_check
        return graph

    monkeypatch.setattr(build_module, "build_graph_from_db", graph_held_before_its_vertices)
    run_id = uuid.uuid4()
    build = asyncio.create_task(
        generate_flow_events(
            flow_id=flow_id,
            background_tasks=BackgroundTasks(),
            event_manager=create_default_event_manager(asyncio.Queue()),
            inputs=InputValueRequest(session=str(flow_id)),
            data=None,
            files=None,
            stop_component_id=None,
            start_component_id=None,
            log_builds=False,
            current_user=active_user,
            run_id=str(run_id),
        )
    )
    try:
        swept = await _sweep_while_held(job_service, gate)
    finally:
        gate.release.set()
        await asyncio.wait_for(build, timeout=30)

    assert swept == [dead_job_id]
    await _assert_completed_cleanly(job_service, run_id)


@pytest.mark.usefixtures("client", "fast_heartbeat")
@pytest.mark.parametrize("trigger", ["manual", "auto_capture"])
async def test_memory_base_ingestion_is_not_swept_while_it_runs(trigger, active_user, monkeypatch):
    from langflow.services.memory_base import ingestion

    job_service = get_job_service()
    dead_job_id = await _dead_job(job_service)
    memory_base = MemoryBase(
        id=uuid.uuid4(),
        name="live_mb",
        flow_id=uuid.uuid4(),
        user_id=active_user.id,
        threshold=1,
        kb_name="live_mb_kb",
        auto_capture=True,
        created_at=datetime.now(timezone.utc),
    )
    memory_session = MemoryBaseSession(id=uuid.uuid4(), memory_base_id=memory_base.id, session_id="sess-1")
    gate = _Gate()
    job_ids: list[uuid.UUID] = []

    async def held_ingestion(*, request) -> dict:
        job_ids.append(request.task_job_id)
        await gate.hold()
        return {}

    # Provider resolution and the message cursor are not what this test is about.
    monkeypatch.setattr(
        ingestion, "resolve_memory_provider_scope", AsyncMock(return_value=MagicMock(memory_base=memory_base))
    )
    monkeypatch.setattr(ingestion, "_get_latest_pending_workflow_job_id", AsyncMock(return_value=None))
    monkeypatch.setattr(ingestion, "_insert_workflow_run", AsyncMock())
    monkeypatch.setattr(ingestion, "count_pending_messages", AsyncMock(return_value=memory_base.threshold))
    monkeypatch.setattr(ingestion, "resolve_kb_username", AsyncMock(return_value="tester"))
    monkeypatch.setattr(
        ingestion, "resolve_embedding_selection", AsyncMock(return_value=("OpenAI", "text-embedding-3-small"))
    )
    monkeypatch.setattr(ingestion, "preflight_memory_provider_use", AsyncMock())
    monkeypatch.setattr(ingestion, "ingest_memory_task", held_ingestion)
    get_or_create_session = AsyncMock(return_value=memory_session)

    if trigger == "manual":
        await ingestion.trigger_ingestion(
            memory_base.id,
            active_user.id,
            active_user.id,
            memory_session.session_id,
            get_mb_or_raise=AsyncMock(return_value=memory_base),
            get_or_create_session=get_or_create_session,
        )
    else:
        await ingestion._maybe_trigger(
            mb=memory_base,
            session_id=memory_session.session_id,
            job_id=None,
            get_or_create_session=get_or_create_session,
        )
    try:
        swept = await _sweep_while_held(job_service, gate)
    finally:
        gate.release.set()

    async def finished() -> None:
        # The run was fired and forgotten, so its terminal write is only visible on the row.
        while (await job_service.get_job_by_job_id(job_ids[0])).status == JobStatus.IN_PROGRESS:  # noqa: ASYNC110
            await asyncio.sleep(0.05)

    await asyncio.wait_for(finished(), timeout=10)
    assert swept == [dead_job_id]
    await _assert_completed_cleanly(job_service, job_ids[0])
