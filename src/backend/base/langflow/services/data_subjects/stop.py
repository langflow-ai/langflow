"""Phase 1 of an erase: refuse what must not be erased, then cut every way new data could be written.

Runs in the approval transaction, so the admin sees the refusal or the stop synchronously.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, update
from sqlmodel import col, or_, select

from langflow.services.data_subjects.errors import DeployedResourcesError, LastAdministratorError
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth.authz import AuthzShare, ShareScope
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.models.jobs.model import ExecutionSignal, Job, JobStatus, SignalType
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.user.model import User
from langflow.services.triggers.cleanup import delete_triggers
from langflow.services.triggers.source_cleanup import preserve_user_cleanup_credentials

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.data_subjects.identity import EndUserKeys

LIVE_JOB_STATUSES = (JobStatus.QUEUED, JobStatus.IN_PROGRESS, JobStatus.SUSPENDED)
MAX_LISTED_RESOURCES = 20


def _owned_flows(user_id: UUID):
    return select(Flow.id).where(Flow.user_id == user_id)


async def deployed_resources(session: AsyncSession, user_id: UUID) -> list[str]:
    """Names of deployments that block erasing this builder."""
    deployments = (
        await session.exec(
            select(Deployment.display_name).where(Deployment.user_id == user_id).limit(MAX_LISTED_RESOURCES)
        )
    ).all()
    attached_versions = select(FlowVersion.id).where(col(FlowVersion.flow_id).in_(_owned_flows(user_id)))
    attachments = (
        await session.exec(
            select(func.count())
            .select_from(FlowVersionDeploymentAttachment)
            .where(
                or_(
                    FlowVersionDeploymentAttachment.user_id == user_id,
                    col(FlowVersionDeploymentAttachment.flow_version_id).in_(attached_versions),
                )
            )
        )
    ).one()
    names = [str(name) for name in deployments]
    if attachments and not names:
        names.append(f"{attachments} deployed flow version(s)")
    return names


async def ensure_builder_erasable(session: AsyncSession, user: User) -> None:
    blocking = await deployed_resources(session, user.id)
    if blocking:
        msg = "Undeploy these resources before erasing the account"
        raise DeployedResourcesError(msg, details={"deployments": blocking})
    await ensure_not_last_administrator(session, user)


async def ensure_not_last_administrator(session: AsyncSession, user: User) -> None:
    if user.is_superuser:
        others = (
            await session.exec(
                select(func.count())
                .select_from(User)
                .where(col(User.is_superuser).is_(True), col(User.is_active).is_(True), User.id != user.id)
            )
        ).one()
        if not others:
            msg = "The last active superuser cannot be erased"
            raise LastAdministratorError(msg)


async def _stop_jobs(session: AsyncSession, where: ColumnElement[bool]) -> int:
    live = list(
        (await session.exec(select(Job.job_id, Job.status).where(where, col(Job.status).in_(LIVE_JOB_STATUSES)))).all()
    )
    if not live:
        return 0
    now = datetime.now(timezone.utc)
    job_ids = [job_id for job_id, _ in live]
    for job_id, status in live:
        if status == JobStatus.IN_PROGRESS:
            session.add(ExecutionSignal(job_id=job_id, signal_type=SignalType.STOP))
    await session.exec(
        update(Job).where(col(Job.job_id).in_(job_ids)).values(status=JobStatus.CANCELLED, finished_timestamp=now)
    )
    return len(job_ids)


async def stop_builder(session: AsyncSession, user: User) -> dict[str, int]:
    """Deactivate the account and close every entry point that runs as it."""
    user.is_active = False
    session.add(user)
    trigger_ids = list((await session.exec(select(Trigger.id).where(Trigger.user_id == user.id))).all())
    await delete_triggers(session, trigger_ids=trigger_ids)
    # Remote subscriptions are torn down after the account goes; seal their tokens while connections exist.
    await preserve_user_cleanup_credentials(session, user_id=user.id)
    keys = await session.exec(delete(ApiKey).where(ApiKey.user_id == user.id))
    public_flows = await session.exec(
        update(Flow)
        .where(Flow.user_id == user.id, Flow.access_type == AccessTypeEnum.PUBLIC)
        .values(access_type=AccessTypeEnum.PRIVATE)
    )
    await session.exec(
        delete(AuthzShare).where(
            AuthzShare.resource_type == "flow",
            AuthzShare.scope == ShareScope.PUBLIC.value,
            col(AuthzShare.resource_id).in_(_owned_flows(user.id)),
        )
    )
    jobs = await _stop_jobs(session, or_(Job.user_id == user.id, col(Job.flow_id).in_(_owned_flows(user.id))))
    return {
        "triggers": len(trigger_ids),
        "api_keys": keys.rowcount or 0,
        "public_flows": public_flows.rowcount or 0,
        "jobs_cancelled": jobs,
    }


async def stop_end_user(session: AsyncSession, keys: EndUserKeys, scope_flow_ids: tuple[UUID, ...]) -> dict[str, int]:
    """Cancel the end user's in-flight runs so none writes after the erase."""
    where = col(Job.job_metadata)["end_user_id"].as_string() == keys.raw_id
    if scope_flow_ids:
        where = where & col(Job.flow_id).in_(scope_flow_ids)
    return {"jobs_cancelled": await _stop_jobs(session, where)}
