"""A run that finishes after a watchdog reconciled it must not undo that verdict.

The heartbeat is a task on the run's own event loop, so a component that blocks
the loop stops the beat while the work is still going. Another worker's watchdog
then sees a stale lease and fails the job as worker_lost. The question this file
pins is what happens when the blocked run finally finishes.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.jobs.service import JobService


@pytest.mark.usefixtures("client")
async def test_a_reconciled_run_is_not_completed_when_it_finally_finishes():
    """The watchdog's worker_lost verdict stands, because a client was already told it."""
    service = JobService()
    job_id = uuid4()
    owner = "worker:1:aaaa"

    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    # The watchdog reconciles the stalled run, exactly as it does in the fleet.
    assert await service.fail_in_progress_job(job_id, error={"type": "worker_lost"})

    # The original run unblocks and reports success.
    won = await service.complete_live_job(job_id, owner=owner)

    assert won is False, "a terminal row must not be flipped back to COMPLETED"
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error == {"type": "worker_lost"}


@pytest.mark.usefixtures("client")
async def test_a_stale_run_does_not_complete_a_job_someone_else_reclaimed():
    """After a requeue, the row belongs to whoever claimed it next.

    Status alone cannot catch this: the row is IN_PROGRESS again, just not ours.
    """
    service = JobService()
    job_id = uuid4()
    first_owner = "worker:1:aaaa"
    second_owner = "worker:2:bbbb"

    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
    await service.update_job_metadata(job_id, {"owner": second_owner})
    await service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    won = await service.complete_live_job(job_id, owner=first_owner)

    assert won is False, "a run must not complete a row another worker owns"
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.IN_PROGRESS


@pytest.mark.usefixtures("client")
async def test_an_ordinary_run_still_completes():
    """The guard must not strand the normal path, including callers with no owner."""
    service = JobService()
    job_id = uuid4()

    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    assert await service.complete_live_job(job_id) is True
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.finished_timestamp is not None


@pytest.mark.usefixtures("client")
async def test_a_run_that_finishes_before_its_first_heartbeat_still_completes():
    """The owner is written by the heartbeat, not at claim time.

    A run short enough to finish before its first beat has no owner on the row.
    Requiring a name match would strand exactly the fastest jobs as IN_PROGRESS.
    """
    service = JobService()
    job_id = uuid4()

    await service.create_job(job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, user_id=uuid4())
    await service.update_job_status(job_id, JobStatus.IN_PROGRESS)

    assert await service.complete_live_job(job_id, owner="worker:1:aaaa") is True
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
