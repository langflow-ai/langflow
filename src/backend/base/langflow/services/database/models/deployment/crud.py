from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import col, delete, func, select

from langflow.services.database.models.deployment.model import Deployment

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
    deployment_id: UUID | str,
) -> Deployment | None:
    deployment_uuid = _parse_uuid(deployment_id, field_name="deployment_id")
    stmt = select(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    return (await db.exec(stmt)).first()


async def list_deployment_rows_page(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_account_id: UUID,
    offset: int,
    limit: int,
) -> list[Deployment]:
    stmt = (
        select(Deployment)
        .where(
            Deployment.user_id == user_id,
            Deployment.provider_account_id == provider_account_id,
        )
        .order_by(col(Deployment.created_at).desc(), col(Deployment.id).desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await db.exec(stmt)).all())


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
    return int((await db.exec(stmt)).one())


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
    deployment_uuid = _parse_uuid(deployment_id, field_name="deployment_id")
    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.id == deployment_uuid,
    )
    result = await db.exec(stmt)
    return int(result.rowcount or 0)


def _parse_uuid(value: UUID | str, *, field_name: str = "value") -> UUID:
    """Parse a UUID from a string or pass through a UUID.

    Raises ValueError with context if the string is not a valid UUID.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            msg = f"{field_name} must not be empty"
            raise ValueError(msg)
        try:
            return UUID(stripped)
        except ValueError:
            msg = f"{field_name} is not a valid UUID: {stripped!r}"
            raise ValueError(msg) from None
    return value
