from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.jobs.model import Job


async def get_jobs_by_flow_id(db: AsyncSession, flow_id: UUID, page: int = 1, size: int = 10) -> list[Job]:
    """Get jobs by flow ID with pagination.

    Args:
        db: Async database session
        flow_id: Flow ID to filter by
        page: Page number (1-indexed)
        size: Number of results per page

    Returns:
        List of Job objects
    """
    # PostgreSQL and other databases with native UUID support
    statement = select(Job).where(Job.flow_id == flow_id).offset((page - 1) * size).limit(size)

    result = await db.exec(statement)
    return list(result.all())


async def get_job_by_job_id(db: AsyncSession, job_id: UUID) -> Job | None:
    """Get job by job ID.

    Args:
        db: Async database session
        job_id: Job ID to filter by

    Returns:
        Job object or None if not found
    """
    # PostgreSQL and other databases with native UUID support
    statement = select(Job).where(Job.job_id == job_id)

    result = await db.exec(statement)
    return result.first()


async def update_job_status(db: AsyncSession, job_id: UUID, status: str) -> Job | None:
    """Update job status.

    Args:
        db: Async database session
        job_id: Job ID to update
        status: New status value

    Returns:
        Updated Job object or None if not found
    """
    result = await db.exec(select(Job).where(Job.job_id == job_id))
    job = result.first()
    if job:
        job.status = status
        db.add(job)
        await db.commit()
        await db.refresh(job)
    return job
