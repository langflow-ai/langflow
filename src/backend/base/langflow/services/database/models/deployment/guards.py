"""Application-level delete guards for deployment-linked resources.

These checks are used by flow/project delete paths to fail fast with a friendly
``DeploymentGuardError`` when dependent deployment links still exist.

Concurrency note:
These are pre-delete existence checks (check-then-delete) implemented as
separate statements, not as one DB-enforced invariant. A different transaction
can commit new dependent rows between the check and the later delete/flush.
Callers should treat these guards as
best-effort protection and combine them with bounded retry/sync behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlmodel import col, delete, select

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    get_friendly_guard_detail,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)


async def check_flow_has_deployed_versions(db: AsyncSession, *, flow_id: UUID) -> None:
    """Raise when the flow still has flow versions attached to deployments.

    This is an app-level pre-delete guard. It intentionally checks for the
    existence of at least one *live* deployment attachment and raises a
    friendly guard error.

    If legacy/orphan attachment rows exist (for example from environments where
    SQLite foreign key cascades were not enforced), this guard prunes them for
    the target flow so they don't permanently block deletion.
    """
    attached = (
        await db.exec(
            select(FlowVersionDeploymentAttachment.id)
            .join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id)
            .join(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
            .where(FlowVersion.flow_id == flow_id)
            .limit(1)
        )
    ).first()
    if attached is not None:
        raise DeploymentGuardError(
            code="FLOW_HAS_DEPLOYED_VERSIONS",
            technical_detail=(
                "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment "
                "for the target flow."
            ),
            detail=get_friendly_guard_detail("FLOW_HAS_DEPLOYED_VERSIONS"),
        )

    stale_attachment_ids = (
        await db.exec(
            select(FlowVersionDeploymentAttachment.id)
            .join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id)
            .outerjoin(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersion.flow_id == flow_id,
                Deployment.id.is_(None),  # deployment no longer exists
            )
        )
    ).all()
    if not stale_attachment_ids:
        return

    await db.exec(
        delete(FlowVersionDeploymentAttachment).where(col(FlowVersionDeploymentAttachment.id).in_(stale_attachment_ids))
    )
    await logger.ainfo(
        "Pruned %d orphan deployment attachment(s) for flow %s",
        len(stale_attachment_ids),
        flow_id,
    )


async def check_project_has_deployments(db: AsyncSession, *, project_id: UUID) -> None:
    """Raise when the project still has deployments.

    This is an app-level pre-delete guard. It intentionally checks for the
    existence of at least one deployment and raises a friendly guard error.
    """
    has_deployments = (await db.exec(select(Deployment.id).where(Deployment.project_id == project_id).limit(1))).first()
    if has_deployments is None:
        return

    raise DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail="DELETE folder blocked: dependent rows exist in deployment for the target project.",
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )
