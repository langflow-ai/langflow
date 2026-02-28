from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import col, delete, func, select

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow_history_deployment_attachment.model import (
    FlowHistoryDeploymentAttachment,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_deployment_row(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    provider_account_id: UUID,
    resource_key: str,
    name: str,
) -> Deployment:
    row = Deployment(
        user_id=user_id,
        project_id=project_id,
        provider_account_id=provider_account_id,
        resource_key=resource_key.strip(),
        name=name.strip(),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


async def get_deployment_row_by_resource_key(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_account_id: UUID,
    resource_key: str,
) -> Deployment | None:
    stmt = select(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.provider_account_id == provider_account_id,
        Deployment.resource_key == resource_key.strip(),
    )
    return (await db.exec(stmt)).first()


async def get_deployment_row(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: str,
) -> Deployment | None:
    normalized_deployment_id = deployment_id.strip()
    if not normalized_deployment_id:
        return None

    try:
        deployment_uuid = UUID(normalized_deployment_id)
    except ValueError:
        return None

    by_id_stmt = select(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    return (await db.exec(by_id_stmt)).first()


async def list_deployment_rows_page(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_account_id: UUID,
    offset: int,
    limit: int,
) -> list[tuple[Deployment, int]]:
    attachment_counts_subquery = (
        select(
            FlowHistoryDeploymentAttachment.deployment_id.label("deployment_id"),
            func.count(func.distinct(FlowHistoryDeploymentAttachment.history_id)).label("attached_count"),
        )
        .where(FlowHistoryDeploymentAttachment.user_id == user_id)
        .group_by(FlowHistoryDeploymentAttachment.deployment_id)
        .subquery()
    )
    stmt = (
        select(
            Deployment,
            func.coalesce(attachment_counts_subquery.c.attached_count, 0).label("attached_count"),
        )
        .outerjoin(attachment_counts_subquery, attachment_counts_subquery.c.deployment_id == Deployment.id)
        .where(
            Deployment.user_id == user_id,
            Deployment.provider_account_id == provider_account_id,
        )
        .order_by(col(Deployment.created_at).desc(), col(Deployment.id).desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.exec(stmt)).all()
    return [(deployment, int(attached_count or 0)) for deployment, attached_count in rows]


async def count_deployment_rows(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_account_id: UUID,
) -> int:
    stmt = select(func.count(Deployment.id)).where(
        Deployment.user_id == user_id,
        Deployment.provider_account_id == provider_account_id,
    )
    return int((await db.exec(stmt)).one() or 0)


async def delete_deployment_row_by_resource_key(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_account_id: UUID,
    resource_key: str,
) -> int:
    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.provider_account_id == provider_account_id,
        Deployment.resource_key == resource_key.strip(),
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)


async def delete_deployment_row_by_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID | str,
) -> int:
    deployment_uuid = UUID(deployment_id) if isinstance(deployment_id, str) else deployment_id
    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)
