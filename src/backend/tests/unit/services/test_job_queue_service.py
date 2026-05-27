import asyncio
from uuid import uuid4

import pytest
from langflow.services.job_queue.service import JobQueueNotFoundError, JobQueueService


@pytest.mark.asyncio
async def test_cleanup_job_passes_user_cancel_reason_and_releases_queue():
    service = JobQueueService()
    job_id = str(uuid4())
    user_id = uuid4()
    started = asyncio.Event()
    cancel_args: list[tuple[object, ...]] = []

    async def cancellable_job():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError as exc:
            cancel_args.append(exc.args)
            raise

    service.create_queue(job_id)
    service.register_job_owner(job_id, user_id)
    service.start_job(job_id, cancellable_job())
    await asyncio.wait_for(started.wait(), timeout=1)

    await service.cleanup_job(job_id)

    assert cancel_args == [("LANGFLOW_USER_CANCELLED",)]
    assert service.get_job_owner(job_id) is None
    with pytest.raises(JobQueueNotFoundError):
        service.get_queue_data(job_id)
