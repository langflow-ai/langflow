"""Heartbeat shutdown must drain database work before runner teardown."""

from __future__ import annotations

import asyncio
import contextlib
from uuid import uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

pytestmark = pytest.mark.real_services


@pytest.mark.parametrize("cancel_during_cleanup", [False, True])
async def test_shutdown_drains_active_heartbeat(real_services_job_service, monkeypatch, cancel_during_cleanup):
    jobs = real_services_job_service
    job_id = uuid4()
    await jobs.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    entered = asyncio.Event()
    release = asyncio.Event()
    stopping = asyncio.Event()
    finished = asyncio.Event()
    cancelled = asyncio.Event()
    original_heartbeat = jobs.heartbeat

    async def heartbeat(job_id, owner):
        entered.set()
        try:
            await release.wait()
            await original_heartbeat(job_id, owner)
            finished.set()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(jobs, "heartbeat", heartbeat)

    async def source(**_kwargs):
        await entered.wait()
        yield b'{"event":"end","data":{}}', "end"

    runner = JobRunner(
        job_service=jobs,
        live_bus=InMemoryLiveBus(),
        adapter=get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t")),
        frame_source=source,
        owner="heartbeat-shutdown-test",
        heartbeat_interval_s=3600,
    )
    original_stop = runner._stop_heartbeat

    async def stop(*args):
        stopping.set()
        await original_stop(*args)

    monkeypatch.setattr(runner, "_stop_heartbeat", stop)
    task = asyncio.create_task(runner.run(job_id=job_id, source_kwargs={}))
    try:
        await asyncio.wait_for(stopping.wait(), timeout=5)
        if cancel_during_cleanup:
            task.cancel()
        # Give the cancellation a turn while the heartbeat is still active.
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.shield(task), timeout=5)
        assert not cancelled.is_set(), "shutdown interrupted the heartbeat database write"
        assert finished.is_set(), "runner returned before its heartbeat finished"
        job = await jobs.get_job_by_job_id(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.job_metadata["owner"] == "heartbeat-shutdown-test"
    finally:
        release.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
