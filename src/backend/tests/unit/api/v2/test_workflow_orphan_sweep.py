"""An orphan sweep must not reap a live sync or stream workflow run.

Sync and live-stream runs create a WORKFLOW job row and run it IN_PROGRESS through
``execute_with_status``, but only the background runner writes a heartbeat. The sweep
used to treat a missing heartbeat as stale at any age, so every sweep (each pod boot,
and every watchdog tick with ``job_queue_type=redis``) failed every in-flight sync and
stream run with ``worker_lost``: GET status returned 500 JOB_FAILED mid-run, and the
row finished COMPLETED with the stale error and a ``run_failed`` event.

Each test slows the graph so the run is still in flight when the sweep fires.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.interface import components
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.jobs.service import JobService
from lfx.graph.graph.base import Graph
from sqlmodel import select

SLOW_S = 1.5


@pytest.fixture
def slow_graph(monkeypatch):
    original = Graph.check_and_handle_pause

    async def slow(self):
        await asyncio.sleep(SLOW_S)
        return await original(self)

    monkeypatch.setattr(Graph, "check_and_handle_pause", slow)


async def _make_flow(user_id: UUID) -> UUID:
    node = deepcopy(components.component_cache.all_types_dict["input_output"]["ChatInput"])
    node["template"]["should_store_message"]["value"] = False
    payload = {
        "nodes": [{"id": "ChatInput-qa", "data": {"id": "ChatInput-qa", "type": "ChatInput", "node": node}}],
        "edges": [],
    }
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"orphan-sweep-{flow_id.hex[:6]}", data=payload, user_id=user_id))
    return flow_id


async def _job_for_flow(flow_id: UUID) -> Job | None:
    async with session_scope() as session:
        return (await session.exec(select(Job).where(Job.flow_id == flow_id))).first()


async def _wait_in_progress(flow_id: UUID, timeout: float = 10.0) -> Job:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        job = await _job_for_flow(flow_id)
        if job is not None and job.status == JobStatus.IN_PROGRESS:
            return job
        await asyncio.sleep(0.05)
    msg = "job never reached IN_PROGRESS"
    raise AssertionError(msg)


async def _assert_finished_clean(flow_id: UUID) -> None:
    final = await _job_for_flow(flow_id)
    assert final.status == JobStatus.COMPLETED
    assert final.error is None
    assert await JobService().read_events(final.job_id) == []


@pytest.mark.usefixtures("slow_graph")
@pytest.mark.parametrize("mode", ["sync", "stream"])
async def test_sweep_spares_live_run(client, created_api_key, mode):
    """One sweep pass mid-run (a pod boot, or a watchdog tick) leaves the live run alone."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = await _make_flow(created_api_key.user_id)
    body = {"flow_id": str(flow_id), "mode": mode, "input_value": "hello"}

    post = asyncio.create_task(client.post("api/v2/workflows", json=body, headers=headers))
    job = await _wait_in_progress(flow_id)
    assert not (job.job_metadata or {}).get("heartbeat_at")

    swept = await JobService().sweep_orphans(lease_ttl_s=get_settings_service().settings.background_lease_ttl_s)
    assert job.job_id not in swept
    assert (await _job_for_flow(flow_id)).status == JobStatus.IN_PROGRESS
    if mode == "sync":
        status_mid = await client.get("api/v2/workflows", params={"job_id": str(job.job_id)}, headers=headers)
        assert status_mid.status_code == 200, status_mid.text

    response = await post
    assert response.status_code == 200, response.text
    if mode == "sync":
        assert response.json()["status"] == "completed"
    await _assert_finished_clean(flow_id)


@pytest.mark.usefixtures("slow_graph")
async def test_redis_fallback_watchdog_spares_live_sync_run(client, created_api_key):
    """With job_queue_type=redis and no scaled worker, every pod sweeps on the watchdog interval."""
    settings = get_settings_service().settings.model_copy(
        update={"job_queue_type": "redis", "background_watchdog_interval_s": 0.2}
    )
    svc = BackgroundExecutionService(SimpleNamespace(settings=settings))
    assert svc._is_redis  # the fallback state under test
    assert not svc._scaled
    await svc.start()
    try:
        headers = {"x-api-key": created_api_key.api_key}
        flow_id = await _make_flow(created_api_key.user_id)
        body = {"flow_id": str(flow_id), "mode": "sync", "input_value": "hi"}
        post = asyncio.create_task(client.post("api/v2/workflows", json=body, headers=headers))
        await _wait_in_progress(flow_id)
        await asyncio.sleep(SLOW_S / 2)  # several watchdog ticks
        assert (await _job_for_flow(flow_id)).status == JobStatus.IN_PROGRESS

        response = await post
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        await _assert_finished_clean(flow_id)
    finally:
        await svc.stop()
