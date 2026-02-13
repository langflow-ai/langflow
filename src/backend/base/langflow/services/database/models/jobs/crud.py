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
        await db.flush()
        await db.refresh(job)
    return job


async def get_latest_jobs_by_asset_ids(db: AsyncSession, asset_ids: list[UUID]) -> dict[UUID, Job]:
    """Get the latest job for each asset ID in a single query.

    Args:
        db: Async database session
        asset_ids: List of asset IDs to fetch jobs for

    Returns:
        Dictionary mapping asset_id to the latest Job object
    """
    if not asset_ids:
        return {}

    # Query all jobs for the given asset IDs, ordered by created_timestamp descending
    statement = select(Job).where(Job.asset_id.in_(asset_ids)).order_by(Job.created_timestamp.desc())

    result = await db.exec(statement)
    all_jobs = result.all()

    # Build a dictionary with the latest job per asset_id
    latest_jobs: dict[UUID, Job] = {}
    for job in all_jobs:
        if job.asset_id and job.asset_id not in latest_jobs:
            latest_jobs[job.asset_id] = job

    return latest_jobs
