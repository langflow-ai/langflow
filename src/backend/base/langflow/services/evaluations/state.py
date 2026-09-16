"""Atomic evaluation progress, including parent/child submission boundaries."""

from datetime import datetime, timezone

from sqlmodel import col, update

from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.deps import session_scope

ACTIVE = (JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED)


async def write_progress(session, job_id, user_id, version, progress, status):
    """Compare-and-set: stale coordinators cannot overwrite cancellation or completion."""
    result = await session.exec(
        update(Job)
        .where(
            Job.job_id == job_id,
            Job.user_id == user_id,
            Job.type == JobType.EVALUATION,
            col(Job.status).in_(ACTIVE),
            col(Job.result)["version"].as_integer() == version,
        )
        .values(
            result={**progress, "version": version + 1},
            status=status,
            finished_timestamp=None if status in ACTIVE else datetime.now(timezone.utc),
        )
    )
    return result.rowcount == 1


async def save_progress(job, progress, status):
    async with session_scope() as session:
        return await write_progress(session, job.job_id, job.user_id, job.result["version"], progress, status)
