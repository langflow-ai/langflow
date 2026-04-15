from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from sqlmodel import col, select

from langflow.services.database.models.jobs.model import Job, JobStatus


async def get_jobs_by_flow_id(db: AsyncSession, flow_id: UUID, page: int = 1, size: int = 10) -> list[Job]:
    """Get jobs by flow ID with pagination.

    Args:
        db: Async database session
        flow_id: The flow ID to filter jobs by
        page: Page number (1-indexed)
        size: Number of jobs per page

    Returns:
        List of Job objects for the specified flow
    """
    statement = (
        select(Job)
        .where(Job.flow_id == flow_id)
        .order_by(col(Job.created_timestamp).desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.exec(statement)
    return list(result.all())


async def get_job_by_job_id(db: AsyncSession, job_id: UUID) -> Job | None:
    """Get a single job by its UUID.

    Args:
        db: Async database session
        job_id: The job ID to fetch

    Returns:
        Job object or None if not found
    """
    statement = select(Job).where(Job.job_id == job_id)
    result = await db.exec(statement)
    return result.first()


async def update_job_status(db: AsyncSession, job_id: UUID, status: JobStatus) -> Job | None:
    """Update the status of a job.

    Args:
        db: Async database session
        job_id: The job ID to update
        status: The new status value

    Returns:
        Updated Job object or None if not found
    """
    job = await get_job_by_job_id(db, job_id)
    if job:
        job.status = status
        db.add(job)
        await db.flush()
        await db.refresh(job)
    return job


async def get_latest_jobs_by_asset_ids(db: AsyncSession, asset_ids: Sequence[UUID]) -> dict[UUID, Job]:
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
    statement = select(Job).where(col(Job.asset_id).in_(asset_ids)).order_by(col(Job.created_timestamp).desc())

    result = await db.exec(statement)
    all_jobs = result.all()

    # Build a dictionary with the latest job per asset_id
    latest_jobs: dict[UUID, Job] = {}
    for job in all_jobs:
        if job.asset_id and job.asset_id not in latest_jobs:
            latest_jobs[job.asset_id] = job

    return latest_jobs
