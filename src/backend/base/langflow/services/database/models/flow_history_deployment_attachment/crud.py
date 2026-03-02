from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import delete, func, select

from langflow.services.database.models.flow_history_deployment_attachment.model import (
    FlowHistoryDeploymentAttachment,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    history_id: UUID,
    deployment_id: UUID,
    snapshot_id: str | None = None,
) -> FlowHistoryDeploymentAttachment:
    row = FlowHistoryDeploymentAttachment(
        user_id=user_id,
        history_id=history_id,
        deployment_id=deployment_id,
        snapshot_id=snapshot_id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    history_id: UUID,
    deployment_id: UUID,
) -> FlowHistoryDeploymentAttachment | None:
    stmt = select(FlowHistoryDeploymentAttachment).where(
        FlowHistoryDeploymentAttachment.user_id == user_id,
        FlowHistoryDeploymentAttachment.history_id == history_id,
        FlowHistoryDeploymentAttachment.deployment_id == deployment_id,
    )
    return (await db.exec(stmt)).first()


async def list_deployment_attachments(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
) -> list[FlowHistoryDeploymentAttachment]:
    stmt = select(FlowHistoryDeploymentAttachment).where(
        FlowHistoryDeploymentAttachment.user_id == user_id,
        FlowHistoryDeploymentAttachment.deployment_id == deployment_id,
    )
    return list((await db.exec(stmt)).all())


async def list_deployment_attachments_for_history_ids(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
    history_ids: list[UUID],
) -> list[FlowHistoryDeploymentAttachment]:
    if not history_ids:
        return []
    stmt = select(FlowHistoryDeploymentAttachment).where(
        FlowHistoryDeploymentAttachment.user_id == user_id,
        FlowHistoryDeploymentAttachment.deployment_id == deployment_id,
        FlowHistoryDeploymentAttachment.history_id.in_(history_ids),
    )
    return list((await db.exec(stmt)).all())


async def delete_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    history_id: UUID,
    deployment_id: UUID,
) -> int:
    stmt = delete(FlowHistoryDeploymentAttachment).where(
        FlowHistoryDeploymentAttachment.user_id == user_id,
        FlowHistoryDeploymentAttachment.history_id == history_id,
        FlowHistoryDeploymentAttachment.deployment_id == deployment_id,
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)


async def update_deployment_attachment_snapshot_id(
    db: AsyncSession,
    *,
    attachment: FlowHistoryDeploymentAttachment,
    snapshot_id: str | None,
) -> FlowHistoryDeploymentAttachment:
    attachment.snapshot_id = snapshot_id
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
    stmt = delete(FlowHistoryDeploymentAttachment).where(
        FlowHistoryDeploymentAttachment.user_id == user_id,
        FlowHistoryDeploymentAttachment.deployment_id == deployment_id,
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
            FlowHistoryDeploymentAttachment.deployment_id,
            func.count(func.distinct(FlowHistoryDeploymentAttachment.history_id)),
        )
        .where(
            FlowHistoryDeploymentAttachment.user_id == user_id,
            FlowHistoryDeploymentAttachment.deployment_id.in_(deployment_ids),
        )
        .group_by(FlowHistoryDeploymentAttachment.deployment_id)
    )
    rows = (await db.exec(stmt)).all()
    return {deployment_id: int(count) for deployment_id, count in rows}
