from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.utils import parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


def _strip_or_raise(value: str, field_name: str) -> str:
    """Return *value* stripped of whitespace, or raise if blank."""
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return stripped


async def create_deployment(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    deployment_provider_account_id: UUID,
    resource_key: str,
    name: str,
) -> Deployment:
    # The Deployment model has its own field validators, but pre-checking here
    # gives clearer errors and avoids constructing the object.
    resource_key_s = _strip_or_raise(resource_key, "resource_key")
    name_s = _strip_or_raise(name, "name")

    row = Deployment(
        user_id=user_id,
        project_id=project_id,
        deployment_provider_account_id=deployment_provider_account_id,
        resource_key=resource_key_s,
        name=name_s,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("IntegrityError creating deployment: %s", exc)
        msg = f"Deployment conflicts with an existing record (resource_key={resource_key!r}, name={name!r})"
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


async def update_deployment(
    db: AsyncSession,
    *,
    deployment: Deployment,
    name: str | None = None,
    project_id: UUID | None = None,
) -> Deployment:
    if name is not None:
        deployment.name = _strip_or_raise(name, "name")
    if project_id is not None:
        deployment.project_id = project_id
    deployment.updated_at = datetime.now(timezone.utc)
    db.add(deployment)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        await logger.aerror("IntegrityError updating deployment id=%s: %s", deployment.id, exc)
        msg = "Deployment update conflicts with an existing record"
        raise ValueError(msg) from exc
    await db.refresh(deployment)
    return deployment


async def list_deployments_page(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    offset: int,
    limit: int,
    flow_version_ids: list[UUID] | None = None,
) -> list[tuple[Deployment, int, list[str]]]:
    if offset < 0:
        msg = "offset must be greater than or equal to 0"
        raise ValueError(msg)
    if limit <= 0:
        msg = "limit must be greater than 0"
        raise ValueError(msg)

    attachment_counts_subquery = (
        select(
            FlowVersionDeploymentAttachment.deployment_id.label("deployment_id"),
            func.count(func.distinct(FlowVersionDeploymentAttachment.flow_version_id)).label("attached_count"),
        )
        .where(FlowVersionDeploymentAttachment.user_id == user_id)
        .group_by(FlowVersionDeploymentAttachment.deployment_id)
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
            Deployment.deployment_provider_account_id == deployment_provider_account_id,
        )
    )
    if flow_version_ids:
        matched_deployments_subquery = (
            select(FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                FlowVersionDeploymentAttachment.flow_version_id.in_(flow_version_ids),
            )
            .group_by(FlowVersionDeploymentAttachment.deployment_id)
            .subquery()
        )
        stmt = stmt.join(
            matched_deployments_subquery,
            matched_deployments_subquery.c.deployment_id == Deployment.id,
        )
    stmt = stmt.order_by(col(Deployment.created_at).desc(), col(Deployment.id).desc()).offset(offset).limit(limit)
    rows = (await db.exec(stmt)).all()
    deployment_rows = [(deployment, int(attached_count or 0)) for deployment, attached_count in rows]
    if not flow_version_ids or not deployment_rows:
        return [(deployment, attached_count, []) for deployment, attached_count in deployment_rows]

    deployment_ids = [deployment.id for deployment, _ in deployment_rows]
    matched_rows = (
        await db.exec(
            select(
                FlowVersionDeploymentAttachment.deployment_id,
                FlowVersionDeploymentAttachment.flow_version_id,
            ).where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                FlowVersionDeploymentAttachment.deployment_id.in_(deployment_ids),
                FlowVersionDeploymentAttachment.flow_version_id.in_(flow_version_ids),
            )
        )
    ).all()
    matched_flow_version_ids_by_deployment: dict[UUID, list[str]] = {}
    for deployment_id, flow_version_id in matched_rows:
        existing = matched_flow_version_ids_by_deployment.setdefault(deployment_id, [])
        flow_version_id_str = str(flow_version_id)
        if flow_version_id_str not in existing:
            existing.append(flow_version_id_str)

    return [
        (
            deployment,
            attached_count,
            matched_flow_version_ids_by_deployment.get(deployment.id, []),
        )
        for deployment, attached_count in deployment_rows
    ]


async def count_deployments_by_provider(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    flow_version_ids: list[UUID] | None = None,
) -> int:
    stmt = select(func.count(Deployment.id)).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
    )
    if flow_version_ids:
        matched_deployments_subquery = (
            select(FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                FlowVersionDeploymentAttachment.flow_version_id.in_(flow_version_ids),
            )
            .group_by(FlowVersionDeploymentAttachment.deployment_id)
            .subquery()
        )
        stmt = stmt.join(
            matched_deployments_subquery,
            matched_deployments_subquery.c.deployment_id == Deployment.id,
        )
    return int((await db.exec(stmt)).one() or 0)


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
        await logger.aerror(
            "DELETE rowcount was None for deployment resource_key=%r -- "
            "database driver may not support rowcount for DELETE statements",
            resource_key,
        )
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
        await logger.aerror(
            "DELETE rowcount was None for deployment id=%s -- "
            "database driver may not support rowcount for DELETE statements",
            deployment_uuid,
        )
    return int(result.rowcount or 0)
