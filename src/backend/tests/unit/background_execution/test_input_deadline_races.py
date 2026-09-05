"""A stale timeout scan must not overwrite a newer HITL decision or deadline."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.real_services
@pytest.mark.no_blockbuster
@pytest.mark.parametrize("transition", ["resume", "complete", "cancel", "new_deadline", "other_sweep"])
async def test_stale_input_deadline_scan_preserves_winning_transition(
    real_services_job_service, monkeypatch, transition
):
    """Interleave another real transaction after the sweep reads its candidates."""
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=uuid4(), user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.SUSPENDED)
    await service.update_job_metadata(
        job_id,
        {"input_deadline_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()},
    )
    await service.save_checkpoint(job_id, "graph", "saved checkpoint")

    original_exec = AsyncSession.exec
    scan_read = False

    async def exec_with_concurrent_transition(session, statement, *args, **kwargs):
        nonlocal scan_read
        result = await original_exec(session, statement, *args, **kwargs)
        if not scan_read:
            scan_read = True
            if transition == "resume":
                assert await service.claim_suspended_for_resume(job_id, owner="resuming-worker")
            elif transition == "complete":
                await service.update_job_status(job_id, JobStatus.COMPLETED, finished_timestamp=True)
            elif transition == "cancel":
                assert await service.claim_suspended_for_cancel(job_id)
            elif transition == "new_deadline":
                await service.update_job_metadata(
                    job_id,
                    {"input_deadline_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
                )
            else:
                assert await service.sweep_input_deadlines() == [job_id]
        return result

    with monkeypatch.context() as context:
        context.setattr(AsyncSession, "exec", exec_with_concurrent_transition)
        expired = await service.sweep_input_deadlines()

    assert expired == []
    job = await service.get_job_by_job_id(job_id)
    expected_status = {
        "resume": JobStatus.IN_PROGRESS,
        "complete": JobStatus.COMPLETED,
        "cancel": JobStatus.CANCELLED,
        "new_deadline": JobStatus.SUSPENDED,
        "other_sweep": JobStatus.FAILED,
    }[transition]
    assert job.status == expected_status
    events = await service.read_events(job_id)
    timeout_events = [event for event in events if event.event_type == "input_timed_out"]
    assert len(timeout_events) == (1 if transition == "other_sweep" else 0)
    checkpoint = await service.load_checkpoint(job_id, "graph")
    assert checkpoint == (None if transition == "other_sweep" else "saved checkpoint")
    if transition != "other_sweep":
        assert job.error is None
