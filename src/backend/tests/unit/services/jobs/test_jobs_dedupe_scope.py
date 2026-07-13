"""create_job dedupe must be scoped per-user, not global.

A client-controlled idempotency_key flows into dedupe_key. A GLOBAL dedupe
count lets user A collide with / DoS user B's key (and the resulting error
leaks that a job with that key exists somewhere). The uniqueness must be scoped
to the owner.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.jobs.exceptions import DuplicateJobError
from langflow.services.jobs.service import JobService


@pytest.mark.usefixtures("client")
async def test_dedupe_is_scoped_per_user():
    service = JobService()
    user_a = uuid4()
    user_b = uuid4()

    # User A reserves a human-meaningful key.
    await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=user_a, dedupe_key="daily-report")

    # User B using the SAME key must NOT collide with A's job.
    job_b = await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=user_b, dedupe_key="daily-report")
    assert job_b is not None


@pytest.mark.usefixtures("client")
async def test_dedupe_still_blocks_same_user():
    service = JobService()
    user_a = uuid4()
    await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=user_a, dedupe_key="k1")

    # Same user, same key, still active -> duplicate is rejected (unchanged behaviour).
    with pytest.raises(DuplicateJobError):
        await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=user_a, dedupe_key="k1")


@pytest.mark.usefixtures("client")
async def test_dedupe_ownerless_still_blocks():
    """Single-tenant AUTO_LOGIN style (user_id=None) keeps a global dedupe floor."""
    service = JobService()
    await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=None, dedupe_key="kx")
    with pytest.raises(DuplicateJobError):
        await service.create_job(job_id=uuid4(), flow_id=uuid4(), user_id=None, dedupe_key="kx")
