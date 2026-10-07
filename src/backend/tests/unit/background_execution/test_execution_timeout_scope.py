"""The sync HTTP ceiling must not bound a background run; JobRunner must.

Before the fix, ``_stream_event_frames`` always applied ``workflow_execution_timeout``,
so it nested inside the runner's ``asyncio.wait_for`` and won. That capped every
background job at the sync ceiling and made the documented
``background_job_timeout=None`` ("no timeout") unreachable.

Real JobService, real migrated SQLite, real dispatcher, real runner. Only the ceiling
and the work duration are shrunk so the tests stay fast.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v2 import workflow_execution as wf_exec
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner
from langflow.services.database.models.jobs.model import JobStatus
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.converters import ParsedWorkflowRun


def _source(adapter, *, mode: str, background: bool):
    """Drive the real dispatcher.

    ``background=True`` mirrors the production background call site, which passes
    ``execution_timeout=None``.

    ``expose_error_details=True`` mirrors a flow owner running their own flow, which is
    what the production call sites pass for that case. Without it the terminal error is
    replaced with the generic client-facing string, and the ceiling assertion below could
    no longer tell a timeout apart from any other failure.
    """
    extra = {"execution_timeout": None} if background else {}

    async def _run(**_kwargs):
        async for frame, event_type in wf_exec._stream_event_frames(
            adapter=adapter,
            flow_id=uuid4(),
            flow_name="flow",
            background_tasks=SimpleNamespace(add_task=lambda *_a, **_k: None),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode=mode),
            current_user=SimpleNamespace(id=uuid4()),
            protocol="v2.background" if background else "v2",
            expose_error_details=True,
            **extra,
        ):
            yield frame, event_type

    return _run


def _slow_build(work_s: float):
    async def _build(**kwargs):
        await asyncio.sleep(work_s)
        queue = kwargs["event_manager"].queue
        queue.put_nowait(("end", json.dumps({"event": "end", "data": {}}).encode(), time.time()))
        await queue.put((None, None, time.time()))

    return _build


async def _run_job(job_service, *, ceiling, work, job_timeout, monkeypatch, background=True, mode="background"):
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    monkeypatch.setattr(wf_exec, "_resolve_execution_timeout", lambda: ceiling)
    monkeypatch.setattr(wf_exec, "generate_flow_events", _slow_build(work))
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=_source(adapter, mode=mode, background=background),
        job_timeout=job_timeout,
    )
    await runner.run(job_id=job_id, source_kwargs={"job_id": job_id})
    return await job_service.get_job_by_job_id(job_id)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_background_run_outlives_the_sync_ceiling(real_services_job_service, monkeypatch) -> None:
    """background_job_timeout=None means no timeout, even past the sync ceiling."""
    job = await _run_job(real_services_job_service, ceiling=0.05, work=0.5, job_timeout=None, monkeypatch=monkeypatch)
    assert job.status == JobStatus.COMPLETED
    assert job.error is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_background_job_timeout_now_governs(real_services_job_service, monkeypatch) -> None:
    """With background_job_timeout set, the runner bounds the run and marks it TIMED_OUT."""
    job = await _run_job(real_services_job_service, ceiling=60.0, work=5.0, job_timeout=0.05, monkeypatch=monkeypatch)
    assert job.status == JobStatus.TIMED_OUT


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_stream_mode_still_enforces_the_ceiling(real_services_job_service, monkeypatch) -> None:
    """Regression guard: a caller that does NOT opt out still gets the settings ceiling."""
    job = await _run_job(
        real_services_job_service,
        ceiling=0.05,
        work=5.0,
        job_timeout=None,
        monkeypatch=monkeypatch,
        background=False,
        mode="stream",
    )
    assert job.status == JobStatus.FAILED
    assert "timed out" in str(job.error).lower()
