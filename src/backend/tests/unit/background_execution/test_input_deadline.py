"""Input deadline for suspended HITL runs (LE-1452) against a real JobService.

Two independent halves: (1) paused time never counts against the compute timeout —
a run resumed after sitting suspended still completes; (2) an optional
``background_input_deadline_s`` budget that the sweep enforces by FAILing overdue
SUSPENDED rows with ``input_timed_out`` (terminal status + durable event + closed bus).

The deadline is simulated deterministically (no sleeps) by stamping the run with a
negative budget so its ``input_deadline_at`` is already in the past.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import HUMAN_INPUT_REQUIRED_EVENT, JobRunner
from langflow.services.database.models.jobs.model import JobStatus


def _frame(event_type: str, data: dict) -> tuple[bytes, str]:
    return (json.dumps({"event": event_type, "data": data}).encode(), event_type)


def _pause_source(payload: dict):
    async def _source(**_kwargs):
        yield _frame("add_message", {"text": "working…"})
        yield (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)

    return _source


def _runner(job_service, job_id, source, *, input_deadline_s=None):
    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    return JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=adapter,
        frame_source=source,
        input_deadline_s=input_deadline_s,
    )


async def _suspend_a_job(job_service, *, request_id="req-1", input_deadline_s=None):
    user_id, flow_id, job_id = uuid4(), uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=user_id)
    await job_service.update_job_metadata(job_id, {"request": {"flow_id": str(flow_id), "stream_protocol": "langflow"}})
    payload = {"reason": "human_input_required", "request_id": request_id, "options": ["approve", "reject"]}
    await _runner(job_service, job_id, _pause_source(payload), input_deadline_s=input_deadline_s).run(
        job_id=job_id, source_kwargs={}
    )
    return user_id, job_id


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspend_stamps_input_deadline_when_budget_set(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=3600)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED
    assert (job.job_metadata or {}).get("input_deadline_at")


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspend_does_not_stamp_when_budget_disabled(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=None)

    job = await job_service.get_job_by_job_id(job_id)
    assert (job.job_metadata or {}).get("input_deadline_at") is None


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_sweep_fails_overdue_suspended_run(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=-1)

    failed = await job_service.sweep_input_deadlines()

    assert job_id in failed
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error == {"type": "input_timed_out"}
    assert job.finished_timestamp is not None
    events = await job_service.read_events(job_id)
    assert any(e.event_type == "input_timed_out" for e in events)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_sweep_leaves_not_yet_due_run_suspended(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=3600)

    failed = await job_service.sweep_input_deadlines()

    assert job_id not in failed
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_sweep_ignores_run_without_deadline(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=None)

    failed = await job_service.sweep_input_deadlines()

    assert job_id not in failed
    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_orphan_and_deadline_sweeps_both_spare_a_fresh_suspended_row(real_services_job_service) -> None:
    job_service = real_services_job_service
    _user_id, job_id = await _suspend_a_job(job_service, input_deadline_s=3600)

    await job_service.sweep_orphans()
    await job_service.sweep_input_deadlines()

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED


class _StubUser:
    def __init__(self, user_id):
        self.id = user_id


def _completing_factory(**_kwargs):
    async def _source(**_kw):
        yield _frame("end", {})

    return _source


async def _wait_for_status(job_service, job_id, target, *, attempts=100):
    import asyncio

    for _ in range(attempts):
        job = await job_service.get_job_by_job_id(job_id)
        if job is not None and job.status == target:
            return job
        await asyncio.sleep(0.05)
    return await job_service.get_job_by_job_id(job_id)


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_paused_time_does_not_count_against_compute_timeout(real_services_job_service) -> None:
    """A run resumed after sitting suspended still completes.

    The compute timeout never accrues across the suspend window (resume re-enqueues a
    fresh pass), so a small ``background_job_timeout`` does not kill a resumed run.
    """
    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = real_services_job_service
    user_id, job_id = await _suspend_a_job(job_service, request_id="req-pause", input_deadline_s=None)

    settings = get_settings_service().settings
    original = settings.background_job_timeout
    settings.background_job_timeout = 1.0
    svc = BackgroundExecutionService(settings_service=get_settings_service(), frame_source_factory=_completing_factory)
    await svc.start()
    try:
        accepted = await svc.resume_job(job_id, _StubUser(user_id), request_id="req-pause", decision={"choice": "go"})
        assert accepted
        job = await _wait_for_status(job_service, job_id, JobStatus.COMPLETED)
    finally:
        settings.background_job_timeout = original
        await svc.stop()

    assert job.status == JobStatus.COMPLETED


def test_input_deadline_setting_defaults_none_and_is_independent_of_compute_timeout() -> None:
    from lfx.services.settings.groups.runtime import RuntimeSettings

    assert RuntimeSettings().background_input_deadline_s is None
    configured = RuntimeSettings(background_input_deadline_s=600)
    assert configured.background_input_deadline_s == 600.0
    assert configured.background_job_timeout is None
