from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.utils import parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


async def create_deployment(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    deployment_provider_account_id: UUID,
    resource_key: str,
    name: str,
) -> Deployment:
    row = Deployment(
        user_id=user_id,
        project_id=project_id,
        deployment_provider_account_id=deployment_provider_account_id,
        resource_key=resource_key.strip(),
        name=name.strip(),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        msg = f"Deployment already exists (resource_key={resource_key!r}, name={name!r})"
        raise ValueError(msg) from exc
    await db.refresh(row)
    return row


async def get_deployment_by_resource_key(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    resource_key: str,
) -> Deployment | None:
    stmt = select(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
        Deployment.resource_key == resource_key.strip(),
    )
    return (await db.exec(stmt)).first()


async def get_deployment(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID | str,
) -> Deployment | None:
    deployment_uuid = parse_uuid(deployment_id, field_name="deployment_id")
    stmt = select(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    return (await db.exec(stmt)).first()


async def list_deployments_page(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    offset: int,
    limit: int,
) -> list[Deployment]:
    stmt = (
        select(Deployment)
        .where(
            Deployment.user_id == user_id,
            Deployment.deployment_provider_account_id == deployment_provider_account_id,
        )
        .order_by(col(Deployment.created_at).desc(), col(Deployment.id).desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await db.exec(stmt)).all())


async def count_deployments(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
) -> int:
    stmt = select(func.count(Deployment.id)).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
    )
    return int((await db.exec(stmt)).one())


async def delete_deployment_by_resource_key(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    resource_key: str,
) -> int:
    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
        Deployment.resource_key == resource_key.strip(),
    )
    result = await db.exec(stmt)
    if result.rowcount is None:
        await logger.awarning("DELETE rowcount was None for deployment resource_key=%r", resource_key)
    return int(result.rowcount or 0)


async def delete_deployment_by_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID | str,
) -> int:
    deployment_uuid = parse_uuid(deployment_id, field_name="deployment_id")
    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    result = await db.exec(stmt)
    if result.rowcount is None:
        await logger.awarning("DELETE rowcount was None for deployment id=%s", deployment_uuid)
    return int(result.rowcount or 0)
