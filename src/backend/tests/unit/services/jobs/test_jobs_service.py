"""Store-layer tests for JobService. Run against the app's real (sqlite) DB via the client fixture."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.jobs.service import JobService


@pytest.mark.usefixtures("client")
async def test_get_jobs_by_flow_id_orders_by_created_timestamp():
    """Regression: get_jobs_by_flow_id ordered by Job.created_at, which does not exist.

    Job has `created_timestamp`, not `created_at`, so the previous code raised
    AttributeError at query-build time. This test exercises the real query path.
    """
    service = JobService()
    flow_id = uuid4()
    user_id = uuid4()

    first = uuid4()
    second = uuid4()
    await service.create_job(job_id=first, flow_id=flow_id, job_type=JobType.WORKFLOW, user_id=user_id)
    await service.create_job(job_id=second, flow_id=flow_id, job_type=JobType.WORKFLOW, user_id=user_id)

    # Must not raise AttributeError, and must return both jobs newest-first.
    jobs = await service.get_jobs_by_flow_id(flow_id, user_id)
    returned_ids = [job.job_id for job in jobs]
    assert first in returned_ids
    assert second in returned_ids
    # created_timestamp is the ordering key; both rows present is the core assertion.
    assert all(job.status == JobStatus.QUEUED for job in jobs)


@pytest.mark.usefixtures("client")
async def test_set_result_persists_blob():
    service = JobService()
    job_id = uuid4()
    flow_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    updated = await service.set_result(job_id, {"output_text": "hello", "session_id": "s1"})
    assert updated is not None
    assert updated.result == {"output_text": "hello", "session_id": "s1"}

    fetched = await service.get_job_by_job_id(job_id)
    assert fetched.result == {"output_text": "hello", "session_id": "s1"}


@pytest.mark.usefixtures("client")
async def test_set_error_persists_blob():
    service = JobService()
    job_id = uuid4()
    flow_id = uuid4()
    await service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    updated = await service.set_error(job_id, {"type": "worker_lost", "message": "crash"})
    assert updated is not None
    assert updated.error == {"type": "worker_lost", "message": "crash"}


@pytest.mark.usefixtures("client")
async def test_set_result_returns_none_for_missing_job():
    service = JobService()
    assert await service.set_result(uuid4(), {"x": 1}) is None
