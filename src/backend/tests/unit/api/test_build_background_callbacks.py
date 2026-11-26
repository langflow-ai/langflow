"""Side effects a /build job schedules must run after the POST response is sent (#16307).

``start_flow_build`` returns a job id and runs the build as a detached task. FastAPI
executes the request's ``BackgroundTasks`` once the POST response is sent, so any
callback the build queued on that object afterwards was silently dropped: no
``vertex_build`` rows, no telemetry, no deferred trace teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import anyio
import pytest
from fastapi import BackgroundTasks
from langflow.api import build
from langflow.api.limited_background_tasks import LimitVertexBuildBackgroundTasks
from langflow.events.event_manager import create_default_event_manager
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import get_queue_service, get_settings_service, get_telemetry_service, session_scope
from lfx.graph.graph.base import Graph
from lfx.graph.utils import log_vertex_build
from sqlmodel import select

from tests.unit.build_utils import create_flow, get_build_events


@pytest.fixture(autouse=True)
def allow_custom_components(monkeypatch):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")


class HeldQueue:
    """Queue service that hands the build coroutine back instead of starting it."""

    def __init__(self):
        self.task_coro = None

    def create_queue(self, _job_id):
        event_manager = create_default_event_manager(asyncio.Queue())
        return event_manager.queue, event_manager

    def start_job(self, _job_id, task_coro):
        self.task_coro = task_coro


@pytest.fixture
def telemetry(monkeypatch):
    service = get_telemetry_service()
    mocks = SimpleNamespace(
        component=AsyncMock(),
        component_inputs=AsyncMock(),
        playground=AsyncMock(),
    )
    monkeypatch.setattr(service, "log_package_component", mocks.component)
    monkeypatch.setattr(service, "log_package_component_inputs", mocks.component_inputs)
    monkeypatch.setattr(service, "log_package_playground", mocks.playground)
    return mocks


@pytest.fixture
def trace_end(monkeypatch):
    # Keep the real in-context closure; observe the exporter boundary it calls.
    mock = AsyncMock()
    monkeypatch.setattr(Graph, "end_all_traces", mock)
    return mock


async def _vertex_build_rows(flow_id: UUID) -> list[VertexBuildTable]:
    async with session_scope() as session:
        return list((await session.exec(select(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id))).all())


async def _start_held_build(*, flow_id, flow, user, request_tasks, queue, **overrides):
    kwargs = {
        "flow_id": flow_id,
        "background_tasks": request_tasks,
        "inputs": None,
        "data": None,
        "files": None,
        "stop_component_id": None,
        "start_component_id": None,
        "log_builds": True,
        "current_user": user,
        "provider_policy_flow": flow,
        "queue_service": queue,
    }
    kwargs.update(overrides)
    return await build.start_flow_build(**kwargs)


async def _load_flow(flow_id: UUID) -> Flow:
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
    assert flow is not None
    return flow


# --- Real driver -----------------------------------------------------------------


async def test_queued_build_runs_callbacks_after_request_queue_was_executed(
    client, active_user, logged_in_headers, json_memory_chatbot_no_llm, telemetry, trace_end
):
    """The job starts only after FastAPI executed the request queue; its side effects still happen."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    flow = await _load_flow(flow_id)
    request_tasks = LimitVertexBuildBackgroundTasks()
    queue = HeldQueue()

    await _start_held_build(flow_id=flow_id, flow=flow, user=active_user, request_tasks=request_tasks, queue=queue)
    await request_tasks()  # FastAPI sent the POST response; the build has not started yet.
    with anyio.fail_after(30):
        await queue.task_coro

    rows = await _vertex_build_rows(flow_id)
    assert rows, "every logged vertex of a queued build must persist a vertex_build row"
    assert all(row.valid for row in rows)
    assert telemetry.component.await_count >= len(rows)
    assert all(call.args[0].component_success for call in telemetry.component.await_args_list)
    telemetry.playground.assert_awaited_once()
    assert telemetry.playground.await_args.args[0].playground_success is True
    # One direct call at the end of a successful build, plus the callback queued after the last vertex.
    assert trace_end.await_count == 2

    # The request queue never received the job's work, so it cannot run anything twice.
    assert not request_tasks.tasks
    awaited = telemetry.component.await_count
    await request_tasks()
    assert telemetry.component.await_count == awaited


async def test_queued_build_runs_callbacks_for_a_failing_vertex(
    client, active_user, logged_in_headers, json_memory_chatbot_no_llm, telemetry, trace_end, monkeypatch
):
    """A failed vertex still persists its build, reports failed telemetry and ends traces with the error."""
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    flow = await _load_flow(flow_id)
    real_build_vertex = Graph.build_vertex
    failure = ValueError("vertex failed on purpose")
    failed_vertex_ids = []

    async def build_vertex(self, vertex_id, **kwargs):
        if vertex_id.startswith("ChatOutput"):
            failed_vertex_ids.append(vertex_id)
            raise failure
        return await real_build_vertex(self, vertex_id, **kwargs)

    monkeypatch.setattr(Graph, "build_vertex", build_vertex)
    request_tasks = LimitVertexBuildBackgroundTasks()
    queue = HeldQueue()

    await _start_held_build(flow_id=flow_id, flow=flow, user=active_user, request_tasks=request_tasks, queue=queue)
    await request_tasks()
    with anyio.fail_after(30), contextlib.suppress(Exception):
        # Whether the driver re-raises a vertex failure is not what this test is about.
        await queue.task_coro

    assert failed_vertex_ids, "the flow must reach the failing vertex for this test to mean anything"
    rows = await _vertex_build_rows(flow_id)
    failed_rows = [row for row in rows if row.id in failed_vertex_ids]
    assert failed_rows
    assert not any(row.valid for row in failed_rows)

    component_payloads = [call.args[0] for call in telemetry.component.await_args_list]
    assert any(p.component_id in failed_vertex_ids and not p.component_success for p in component_payloads)
    playground_payloads = [call.args[0] for call in telemetry.playground.await_args_list]
    assert playground_payloads
    # The trace teardown queued in the failing vertex's error branch carries the error.
    assert any(call.args[1:2] == (failure,) for call in trace_end.await_args_list)


async def _wait_for_jobs(job_ids) -> None:
    tasks = {task for job_id in job_ids if (task := get_queue_service().get_queue_data(job_id)[2]) is not None}
    assert tasks
    with anyio.fail_after(30):
        await asyncio.wait(tasks)


async def test_http_queued_and_direct_delivery_persist_the_same_builds(
    client, logged_in_headers, json_memory_chatbot_no_llm, telemetry
):
    """POST /build + GET /events now matches ?event_delivery=direct, and nothing runs twice."""
    queued_flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    copy = json.loads(json_memory_chatbot_no_llm)
    copy.pop("id", None)
    copy["name"] = f"{copy.get('name', 'flow')} (direct)"
    direct_flow_id = await create_flow(client, json.dumps(copy), logged_in_headers)
    body = {"inputs": {"input_value": "hi", "session": "s1"}}

    response = await client.post(f"api/v1/build/{queued_flow_id}/flow", json=body, headers=logged_in_headers)
    assert response.status_code == 200
    queued_job_id = response.json()["job_id"]
    events = await get_build_events(client, queued_job_id, logged_in_headers)
    assert events.status_code == 200
    await _wait_for_jobs([queued_job_id])
    queued_rows = await _vertex_build_rows(queued_flow_id)
    queued_playground = telemetry.playground.await_count

    # The direct stream carries no job id; wait on the jobs this request added.
    jobs_before = set(get_queue_service()._queues)
    response = await client.post(
        f"api/v1/build/{direct_flow_id}/flow?event_delivery=direct", json=body, headers=logged_in_headers
    )
    assert response.status_code == 200
    await _wait_for_jobs(set(get_queue_service()._queues) - jobs_before)
    direct_rows = await _vertex_build_rows(direct_flow_id)

    assert queued_rows
    assert len(queued_rows) == len(direct_rows)
    assert sorted(row.id for row in queued_rows) == sorted(row.id for row in direct_rows)
    assert queued_playground == 1
    assert telemetry.playground.await_count == 2


# --- Job-owned queue lifecycle ---------------------------------------------------


def _stub_build_args():
    return {"flow": SimpleNamespace(id=uuid4()), "user": SimpleNamespace(id=uuid4(), is_superuser=False)}


async def test_callback_failure_does_not_skip_later_callbacks_or_replace_build_error(monkeypatch):
    ran = []

    async def record(value):
        ran.append(value)

    async def fail():
        msg = "callback failed"
        raise RuntimeError(msg)

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]
        tasks.add_task(record, "before")
        tasks.add_task(fail)
        tasks.add_task(record, "after")
        msg = "build failed"
        raise ValueError(msg)

    monkeypatch.setattr(build, "generate_flow_events", driver)
    request_tasks = BackgroundTasks()
    queue = HeldQueue()
    await _start_held_build(flow_id=uuid4(), request_tasks=request_tasks, queue=queue, **_stub_build_args())
    await request_tasks()

    with pytest.raises(ValueError, match="build failed"):
        await queue.task_coro
    assert ran == ["before", "after"]
    assert not request_tasks.tasks


async def test_callbacks_queued_by_callbacks_also_run(monkeypatch):
    ran = []

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]

        async def first():
            ran.append("first")
            tasks.add_task(second)

        async def second():
            ran.append("second")

        tasks.add_task(first)

    monkeypatch.setattr(build, "generate_flow_events", driver)
    queue = HeldQueue()
    await _start_held_build(flow_id=uuid4(), request_tasks=BackgroundTasks(), queue=queue, **_stub_build_args())
    await queue.task_coro
    assert ran == ["first", "second"]


@pytest.mark.parametrize("cancel_during", ["build", "callbacks"])
@pytest.mark.parametrize("cancels", [1, 3])
async def test_cancelled_job_still_runs_queued_callbacks(monkeypatch, cancel_during, cancels):
    """Cancelling the job, even repeatedly while a callback is blocked, does not drop callbacks."""
    ran = []
    build_waiting = asyncio.Event()
    callback_blocked = asyncio.Event()
    release_callback = asyncio.Event()

    async def blocking_callback():
        callback_blocked.set()
        await release_callback.wait()
        ran.append("blocking")

    async def record(value):
        ran.append(value)

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]
        tasks.add_task(blocking_callback)
        tasks.add_task(record, "after")
        if cancel_during == "build":
            build_waiting.set()
            await asyncio.Event().wait()

    monkeypatch.setattr(build, "generate_flow_events", driver)
    queue = HeldQueue()
    await _start_held_build(flow_id=uuid4(), request_tasks=BackgroundTasks(), queue=queue, **_stub_build_args())
    job = asyncio.create_task(queue.task_coro)

    with anyio.fail_after(5):
        if cancel_during == "build":
            await build_waiting.wait()
            job.cancel()
        await callback_blocked.wait()
        for _ in range(cancels):
            job.cancel()
            await asyncio.sleep(0)
        assert not job.done(), "cancellation must not interrupt a running callback"
        release_callback.set()
        with pytest.raises(asyncio.CancelledError):
            await job

    assert ran == ["blocking", "after"]


async def test_job_queue_keeps_the_request_queue_class_and_vertex_log_limit(monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "max_vertex_builds_per_vertex", 1)
    request_tasks = LimitVertexBuildBackgroundTasks()
    seen = {}

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]
        seen["queue"] = tasks
        for value in (1, 2):
            tasks.add_task(log_vertex_build, vertex_id="same", flow_id=uuid4(), valid=True, params=None, data=value)
        seen["retained"] = [task.kwargs["data"] for task in tasks.tasks]
        tasks.tasks.clear()  # This test is about admission, not writing a synthetic row.

    monkeypatch.setattr(build, "generate_flow_events", driver)
    queue = HeldQueue()
    await _start_held_build(flow_id=uuid4(), request_tasks=request_tasks, queue=queue, **_stub_build_args())
    await queue.task_coro

    assert type(seen["queue"]) is LimitVertexBuildBackgroundTasks
    assert seen["queue"] is not request_tasks
    assert seen["retained"] == [2]
