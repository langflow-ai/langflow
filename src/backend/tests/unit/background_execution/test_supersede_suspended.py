"""A new background run supersedes the flow's stale suspended pause.

Re-running a flow while a previous run sits SUSPENDED left both pauses alive: the
pending list piled up, every surface (badge, cards, trace bar) kept offering a
decision nobody could meaningfully answer, and the old checkpoint lingered forever.
Submitting a new run for the same flow + user now cancels the stale suspended runs
first — running jobs are untouched (parallel runs stay supported), and other flows
or users are never affected.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import HUMAN_INPUT_REQUIRED_EVENT, JobRunner
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_settings_service
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

pytestmark = [pytest.mark.real_services, pytest.mark.no_blockbuster]


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode(), event_type)


def _pause_source(request_id: str):
    async def _source(**_kwargs):
        payload = {"reason": "human_input_required", "request_id": request_id, "options": ["approve"]}
        yield (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)

    return _source


async def _suspend_a_job(job_service, *, flow_id, user_id, request_id="req-1"):
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": {"flow_id": str(flow_id), "stream_protocol": "langflow"}})
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=_pause_source(request_id),
    )
    await runner.run(job_id=job_id, source_kwargs={})
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED
    return job_id


def _service() -> BackgroundExecutionService:
    def _end_source(**_kwargs):
        async def _source(**_inner):
            yield _frame("end", {})

        return _source

    return BackgroundExecutionService(get_settings_service(), frame_source_factory=_end_source)


async def test_supersede_cancels_suspended_runs_of_same_flow_and_user(real_services_job_service):
    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    stale_job_id = await _suspend_a_job(job_service, flow_id=flow_id, user_id=user_id)

    superseded = await _service().supersede_suspended_runs(flow_id=flow_id, user_id=user_id)

    assert stale_job_id in superseded
    job = await job_service.get_job_by_job_id(stale_job_id)
    assert job.status == JobStatus.CANCELLED
    assert (job.job_metadata or {}).get("pending_request_id") is None


async def test_supersede_leaves_other_flows_and_users_alone(real_services_job_service):
    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    other_flow_job = await _suspend_a_job(job_service, flow_id=uuid4(), user_id=user_id)
    other_user_job = await _suspend_a_job(job_service, flow_id=flow_id, user_id=uuid4())

    superseded = await _service().supersede_suspended_runs(flow_id=flow_id, user_id=user_id)

    assert superseded == []
    for untouched in (other_flow_job, other_user_job):
        job = await job_service.get_job_by_job_id(untouched)
        assert job.status == JobStatus.SUSPENDED


async def test_submit_supersedes_the_previous_suspended_run(real_services_job_service):
    job_service = real_services_job_service
    flow_id, user_id = uuid4(), uuid4()
    stale_job_id = await _suspend_a_job(job_service, flow_id=flow_id, user_id=user_id)

    service = _service()
    new_job_id = await service.submit(
        flow_id=flow_id,
        request={"flow_id": str(flow_id), "stream_protocol": "langflow"},
        user=SimpleNamespace(id=user_id),
    )

    stale = await job_service.get_job_by_job_id(stale_job_id)
    assert stale.status == JobStatus.CANCELLED
    for _ in range(100):
        new = await job_service.get_job_by_job_id(new_job_id)
        if new.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.05)
    assert new.status == JobStatus.COMPLETED
