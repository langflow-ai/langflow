"""What is still writing to an instance, which the migration pause waits for.

The pause refuses to start while any of this is live, because a write that lands
after the copy began is lost without a report. Nothing here stops anything: a
suspended job holds a person's pending decision, so the admin decides what to cancel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from sqlmodel import col, select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord, KnowledgeBaseStatus
from langflow.services.database.models.trigger.model import TriggerLease
from langflow.services.database.models.user.model import User
from langflow.services.triggers.listeners.replicas import PRESENCE_PREFIX

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# A suspended job waits on a person and writes again when they answer.
_LIVE = (JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED)


async def active_jobs(session: AsyncSession, admin_id: UUID) -> list[dict[str, Any]]:
    """Each job that is queued, running or suspended, and each knowledge base marked as ingesting.

    A job's cancel route answers only the job's owner. The admin gets the request that cancels
    each of their own jobs, and for every other job the name of the owner to ask.
    """
    rows = (
        await session.exec(
            select(Job, Flow.name, KnowledgeBaseRecord.name, User.username)
            .outerjoin(Flow, col(Flow.id) == col(Job.flow_id))
            .outerjoin(KnowledgeBaseRecord, col(KnowledgeBaseRecord.id) == col(Job.asset_id))
            .outerjoin(User, col(User.id) == col(Job.user_id))
            .where(col(Job.status).in_(_LIVE))
            .order_by(col(Job.created_timestamp))
        )
    ).all()
    jobs = [
        {
            "id": str(job.job_id),
            "flow_name": flow_name,
            "knowledge_base": knowledge_base,
            "owner": owner,
            "state": job.status.value,
            "started_at": _utc(job.created_timestamp).isoformat(),
            "cancel": _cancel(job, knowledge_base) if job.user_id in (None, admin_id) else None,
        }
        for job, flow_name, knowledge_base, owner in rows
    ]
    # An ingestion marks its knowledge base, and the copy refuses one that is marked. A mark with no
    # live job is what an ingestion leaves when the server stops under it: there is nothing to cancel.
    listed = {job.asset_id for job, *_ in rows}
    marked = await session.exec(
        select(KnowledgeBaseRecord, User.username)
        .outerjoin(User, col(User.id) == col(KnowledgeBaseRecord.user_id))
        .where(KnowledgeBaseRecord.status == KnowledgeBaseStatus.INGESTING.value)
        .order_by(col(KnowledgeBaseRecord.updated_at))
    )
    jobs += [
        {
            "id": str(knowledge_base.id),
            "flow_name": None,
            "knowledge_base": knowledge_base.name,
            "owner": owner,
            "state": knowledge_base.status,
            "started_at": _utc(knowledge_base.updated_at).isoformat(),
            "cancel": None,
        }
        for knowledge_base, owner in marked
        if knowledge_base.id not in listed
    ]
    return jobs


async def live_listeners(session: AsyncSession) -> list[dict[str, Any]]:
    """Each `langflow listeners` process that is running.

    A listener writes trigger events without making a request, so the pause cannot
    refuse it. Each one renews a lease named after itself while it runs and removes
    the lease when it is stopped.
    """
    leases = await session.exec(select(TriggerLease).where(col(TriggerLease.name).startswith(PRESENCE_PREFIX)))
    now = datetime.now(timezone.utc)
    # A lease that has run out belongs to a listener that was killed.
    return [
        {"holder": lease.owner, "heartbeat_at": _utc(lease.heartbeat_at).isoformat()}
        for lease in leases
        if _utc(lease.expires_at) > now
    ]


def _cancel(job: Job, knowledge_base: str | None) -> dict[str, Any] | None:
    """The whole request that cancels a job through its own route, or None when it has no such route."""
    if job.type == JobType.INGESTION:
        # A memory base's ingestion has no cancel route.
        url = f"/api/v1/knowledge_bases/{quote(knowledge_base, safe='')}/cancel" if knowledge_base else None
        return {"method": "POST", "url": url, "body": None} if url else None
    # Only a background run can be stopped. A sync or streamed run ends with the request that started it.
    request = (job.job_metadata or {}).get("request") or {}
    if request.get("mode") != "background":
        return None
    return {"method": "POST", "url": "/api/v2/workflows/stop", "body": {"job_id": str(job.job_id)}}


def _utc(moment: datetime) -> datetime:
    # SQLite reads a time back without its zone.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
