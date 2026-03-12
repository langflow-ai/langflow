from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import delete, func, select

from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_version_id: UUID,
    deployment_id: UUID,
    provider_snapshot_id: str | None = None,
) -> FlowVersionDeploymentAttachment:
    row = FlowVersionDeploymentAttachment(
        user_id=user_id,
        flow_version_id=flow_version_id,
        deployment_id=deployment_id,
        provider_snapshot_id=provider_snapshot_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Note: rollback handled by asyncsession
        logger.warning(
            "Duplicate or invalid attachment: flow_version=%s deployment=%s — %s",
            flow_version_id,
            deployment_id,
            exc,
        )
        msg = (
            f"Attachment conflicts with an existing record "
            f"(flow_version={flow_version_id}, deployment={deployment_id})"
        )
        raise ValueError(msg) from exc
    await db.refresh(row)
    return row


async def get_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_version_id: UUID,
    deployment_id: UUID,
) -> FlowVersionDeploymentAttachment | None:
    stmt = select(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.flow_version_id == flow_version_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
    )
    return (await db.exec(stmt)).first()


async def list_deployment_attachments(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
) -> list[FlowVersionDeploymentAttachment]:
    stmt = select(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
    )
    return list((await db.exec(stmt)).all())


async def list_deployment_attachments_for_flow_version_ids(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
    flow_version_ids: list[UUID],
) -> list[FlowVersionDeploymentAttachment]:
    if not flow_version_ids:
        return []
    stmt = select(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
        FlowVersionDeploymentAttachment.flow_version_id.in_(flow_version_ids),
    )
    return list((await db.exec(stmt)).all())


async def delete_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_version_id: UUID,
    deployment_id: UUID,
) -> int:
    stmt = delete(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.flow_version_id == flow_version_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)


async def update_deployment_attachment_provider_snapshot_id(
    db: AsyncSession,
    *,
    attachment: FlowVersionDeploymentAttachment,
    provider_snapshot_id: str | None,
) -> FlowVersionDeploymentAttachment:
    attachment.provider_snapshot_id = provider_snapshot_id
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    return attachment


async def delete_deployment_attachments_by_deployment_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
) -> int:
    stmt = delete(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)


async def count_attachments_by_deployment_ids(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_ids: list[UUID],
) -> dict[UUID, int]:
    if not deployment_ids:
        return {}

    stmt = (
        select(
            FlowVersionDeploymentAttachment.deployment_id,
            func.count(func.distinct(FlowVersionDeploymentAttachment.flow_version_id)),
        )
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.deployment_id.in_(deployment_ids),
        )
        .group_by(FlowVersionDeploymentAttachment.deployment_id)
    )
    rows = (await db.exec(stmt)).all()
    return {deployment_id: int(count) for deployment_id, count in rows}
