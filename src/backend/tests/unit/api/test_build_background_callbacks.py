"""Detached builds own their callback lifetime after the HTTP response (#16307)."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import anyio
import pytest
from fastapi import BackgroundTasks
from langflow.api import build
from langflow.api.limited_background_tasks import LimitVertexBuildBackgroundTasks
from langflow.events.event_manager import create_default_event_manager
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.deps import get_settings_service, get_telemetry_service, session_scope
from lfx.graph.graph.base import Graph
from lfx.graph.utils import log_vertex_build
from sqlalchemy import select

from tests.unit.build_utils import create_flow


async def test_queued_graph_persists_logs_and_telemetry_after_response(
    client, active_user, logged_in_headers, json_memory_chatbot_no_llm, monkeypatch
):
    """The actual graph runs after the request queue drains; its callbacks still finish."""
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
    callbacks = LimitVertexBuildBackgroundTasks()
    telemetry = get_telemetry_service()
    component = AsyncMock()
    playground = AsyncMock()
    monkeypatch.setattr(telemetry, "log_package_component", component)
    monkeypatch.setattr(telemetry, "log_package_playground", playground)
    # Keep the real in-context closure, and observe the external trace exporter boundary.
    trace = AsyncMock()
    monkeypatch.setattr(Graph, "end_all_traces", trace)

    class HeldQueue:
        task = None

        def create_queue(self, _job_id):
            event_manager = create_default_event_manager(asyncio.Queue())
            return event_manager.queue, event_manager

        def start_job(self, _job_id, task_coro):
            self.task = task_coro

    queue = HeldQueue()
    await build.start_flow_build(
        flow_id=flow_id,
        background_tasks=callbacks,
        inputs=None,
        data=None,
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=True,
        current_user=active_user,
        provider_policy_flow=flow,
        queue_service=queue,
    )
    await callbacks()  # FastAPI has sent the POST response; the graph has not started.
    with anyio.fail_after(30):
        await queue.task

    async with session_scope() as session:
        rows = (await session.exec(select(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id))).all()
    assert rows, "Successful graph vertices must be persisted by their build job"
    assert component.await_count > 0
    playground.assert_awaited()
    trace.assert_awaited()
    # A later HTTP response must not execute job-owned callbacks twice.
    before = component.await_count
    await callbacks()
    assert component.await_count == before


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_driver_callbacks_finish_once_even_after_failure(monkeypatch, outcome):
    """One callback error cannot suppress later callbacks or replace the build outcome."""
    events = []
    entered = asyncio.Event()
    request_callbacks = BackgroundTasks()

    async def record(value):
        events.append(value)

    async def fail():
        msg = "callback failed"
        raise RuntimeError(msg)

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]
        tasks.add_task(record, "before")
        tasks.add_task(fail)
        tasks.add_task(record, "after")
        entered.set()
        if outcome == "cancel":
            await asyncio.Event().wait()
        if outcome == "error":
            msg = "build failed"
            raise ValueError(msg)

    monkeypatch.setattr(build, "_generate_flow_events", driver)
    await request_callbacks()
    task = asyncio.create_task(build.generate_flow_events(background_tasks=request_callbacks))
    with anyio.fail_after(5):
        await entered.wait()
        if outcome == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif outcome == "error":
            with pytest.raises(ValueError, match="build failed"):
                await task
        else:
            await task
    assert events == ["before", "after"]
    assert not request_callbacks.tasks


async def test_job_queue_retains_vertex_log_limit(monkeypatch):
    """Creating a job-owned queue must preserve the production vertex-build cap."""
    monkeypatch.setattr(get_settings_service().settings, "max_vertex_builds_per_vertex", 1)
    retained = []

    async def driver(**kwargs):
        tasks = kwargs["background_tasks"]
        for value in (1, 2):
            tasks.add_task(log_vertex_build, vertex_id="same", flow_id=uuid4(), data=value)
        retained.extend(task.kwargs["data"] for task in tasks.tasks)
        tasks.tasks.clear()  # This test observes admission, not a synthetic DB log payload.

    monkeypatch.setattr(build, "_generate_flow_events", driver)
    await build.generate_flow_events(background_tasks=LimitVertexBuildBackgroundTasks())
    assert retained == [2]
