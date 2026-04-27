from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services.adapters.deployment.schema import DEPLOYMENT_DESCRIPTION_MAX_LENGTH
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment.orm_guards import ensure_deployment_immutable_fields
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.utils import parse_uuid

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.adapters.deployment.schema import DeploymentType
    from sqlmodel.ext.asyncio.session import AsyncSession


def _strip_or_raise(value: str, field_name: str) -> str:
    """Return *value* stripped of whitespace, or raise if blank."""
    stripped = value.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    return stripped


def _validate_description_max_length(description: str | None) -> str | None:
    """Reject descriptions that exceed the deployment max length."""
    if description is not None and len(description) > DEPLOYMENT_DESCRIPTION_MAX_LENGTH:
        msg = f"description must be at most {DEPLOYMENT_DESCRIPTION_MAX_LENGTH} characters"
        raise ValueError(msg)
    return description


async def create_deployment(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    deployment_provider_account_id: UUID,
    resource_key: str,
    name: str,
    deployment_type: DeploymentType,
    description: str | None = None,
) -> Deployment:
    resource_key_s = _strip_or_raise(resource_key, "resource_key")
    name_s = _strip_or_raise(name, "name")
    description_s = _validate_description_max_length(description)

    row = Deployment(
        user_id=user_id,
        project_id=project_id,
        deployment_provider_account_id=deployment_provider_account_id,
        resource_key=resource_key_s,
        name=name_s,
        deployment_type=deployment_type,
        description=description_s,
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


async def deployment_name_exists(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    name: str,
) -> bool:
    stmt = select(Deployment.id).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
        Deployment.name == name.strip(),
    )
    return (await db.exec(stmt)).first() is not None


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


_UNSET = object()


async def update_deployment(
    db: AsyncSession,
    *,
    deployment: Deployment,
    name: str | None = None,
    project_id: UUID | None = None,
    deployment_type: DeploymentType | object = _UNSET,
    description: str | None | object = _UNSET,
) -> Deployment:
    next_project_id = project_id if project_id is not None else deployment.project_id
    next_deployment_type = deployment.deployment_type if deployment_type is _UNSET else deployment_type
    ensure_deployment_immutable_fields(
        old_project_id=deployment.project_id,
        new_project_id=next_project_id,
        old_deployment_type=deployment.deployment_type,
        new_deployment_type=next_deployment_type,
        old_resource_key=deployment.resource_key,
        new_resource_key=deployment.resource_key,
        old_provider_account_id=deployment.deployment_provider_account_id,
        new_provider_account_id=deployment.deployment_provider_account_id,
    )

    if name is not None:
        deployment.name = _strip_or_raise(name, "name")
    if project_id is not None:
        deployment.project_id = project_id
    if deployment_type is not _UNSET:
        deployment.deployment_type = deployment_type  # type: ignore[assignment]
    if description is not _UNSET:
        deployment.description = _validate_description_max_length(description)  # type: ignore[assignment]
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
    project_id: UUID | None = None,
) -> list[tuple[Deployment, int, list[tuple[UUID, str | None]]]]:
    """Return a page of deployments with attachment counts and matched attachments.

    The third tuple element contains ``(flow_version_id, provider_snapshot_id)``
    pairs for attachments that matched the ``flow_version_ids`` filter (empty
    list when no filter is active).
    """
    if offset < 0:
        msg = "offset must be greater than or equal to 0"
        raise ValueError(msg)
    if limit <= 0:
        msg = "limit must be greater than 0"
        raise ValueError(msg)

    attachment_counts_subquery = (
        select(
            col(FlowVersionDeploymentAttachment.deployment_id).label("deployment_id"),
            func.count(func.distinct(FlowVersionDeploymentAttachment.flow_version_id)).label("attached_count"),
        )
        # Join FlowVersion so stale attachment rows with missing version parent
        # do not inflate attached_count in deployment list responses.
        .join(
            FlowVersion,
            FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id,
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
    if project_id is not None:
        stmt = stmt.where(Deployment.project_id == project_id)
    if flow_version_ids:
        matched_deployments_subquery = (
            select(FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                col(FlowVersionDeploymentAttachment.flow_version_id).in_(flow_version_ids),
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
                FlowVersionDeploymentAttachment.provider_snapshot_id,
            ).where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                col(FlowVersionDeploymentAttachment.deployment_id).in_(deployment_ids),
                col(FlowVersionDeploymentAttachment.flow_version_id).in_(flow_version_ids),
            )
        )
    ).all()
    matched_by_deployment: dict[UUID, list[tuple[UUID, str | None]]] = {}
    for deployment_id, flow_version_id, provider_snapshot_id in matched_rows:
        entries = matched_by_deployment.setdefault(deployment_id, [])
        pair = (flow_version_id, provider_snapshot_id)
        if pair not in entries:
            entries.append(pair)

    return [
        (
            deployment,
            attached_count,
            matched_by_deployment.get(deployment.id, []),
        )
        for deployment, attached_count in deployment_rows
    ]


async def list_deployments_for_flows_with_provider_info(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_ids: list[UUID],
    provider_account_id: UUID | None = None,
) -> list[tuple[Deployment, str]]:
    """Return distinct deployments linked to any flow in *flow_ids* with provider key."""
    if not flow_ids:
        return []

    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.flow_version.model import FlowVersion

    deployment_ids_subquery = (
        select(FlowVersionDeploymentAttachment.deployment_id)
        .join(
            FlowVersion,
            FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id,
        )
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersion.flow_id.in_(flow_ids),
        )
        .distinct()
        .subquery()
    )

    stmt = (
        select(Deployment, DeploymentProviderAccount.provider_key)
        .join(deployment_ids_subquery, deployment_ids_subquery.c.deployment_id == Deployment.id)
        .join(
            DeploymentProviderAccount,
            DeploymentProviderAccount.id == Deployment.deployment_provider_account_id,
        )
        .where(Deployment.user_id == user_id)
        .order_by(
            Deployment.deployment_provider_account_id,
            DeploymentProviderAccount.provider_key,
            Deployment.id,
        )
    )
    if provider_account_id is not None:
        stmt = stmt.where(Deployment.deployment_provider_account_id == provider_account_id)
    return list((await db.exec(stmt)).all())


async def list_project_deployments_with_provider_info(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    provider_account_id: UUID | None = None,
) -> list[tuple[Deployment, str]]:
    """Return project deployments with provider key for provider-scoped sync."""
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount

    stmt = (
        select(Deployment, DeploymentProviderAccount.provider_key)
        .join(
            DeploymentProviderAccount,
            DeploymentProviderAccount.id == Deployment.deployment_provider_account_id,
        )
        .where(
            Deployment.user_id == user_id,
            Deployment.project_id == project_id,
        )
        .order_by(
            Deployment.deployment_provider_account_id,
            DeploymentProviderAccount.provider_key,
            Deployment.id,
        )
    )
    if provider_account_id is not None:
        stmt = stmt.where(Deployment.deployment_provider_account_id == provider_account_id)
    return list((await db.exec(stmt)).all())


async def count_deployments_by_provider(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_provider_account_id: UUID,
    flow_version_ids: list[UUID] | None = None,
    project_id: UUID | None = None,
) -> int:
    stmt = select(func.count(Deployment.id)).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
    )
    if project_id is not None:
        stmt = stmt.where(Deployment.project_id == project_id)
    if flow_version_ids:
        matched_deployments_subquery = (
            select(FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                col(FlowVersionDeploymentAttachment.flow_version_id).in_(flow_version_ids),
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
    resource_key_s = resource_key.strip()
    # Delete attachment rows explicitly before deleting the deployment.
    # This keeps behavior correct even when DB-level FK cascades are disabled
    # (for example, SQLite with foreign_keys=OFF), avoiding orphan attachments.
    deployment_id = (
        await db.exec(
            select(Deployment.id).where(
                Deployment.user_id == user_id,
                Deployment.deployment_provider_account_id == deployment_provider_account_id,
                Deployment.resource_key == resource_key_s,
            )
        )
    ).first()
    if deployment_id is not None:
        await db.exec(
            delete(FlowVersionDeploymentAttachment).where(
                FlowVersionDeploymentAttachment.user_id == user_id,
                FlowVersionDeploymentAttachment.deployment_id == deployment_id,
            )
        )

    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        Deployment.deployment_provider_account_id == deployment_provider_account_id,
        Deployment.resource_key == resource_key_s,
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
    # Delete attachment rows explicitly before deleting the deployment.
    # This keeps behavior correct even when DB-level FK cascades are disabled
    # (for example, SQLite with foreign_keys=OFF), avoiding orphan attachments.
    await db.exec(
        delete(FlowVersionDeploymentAttachment).where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.deployment_id == deployment_uuid,
        )
    )

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


async def delete_deployments_by_ids(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_ids: list[UUID],
) -> int:
    """Delete multiple deployments (and their attachments) in two batched statements."""
    if not deployment_ids:
        return 0
    # Delete attachment rows explicitly before deleting the deployments, mirroring
    # delete_deployment_by_id so behavior stays correct when DB-level FK cascades
    # are disabled (for example, SQLite with foreign_keys=OFF).
    await db.exec(
        delete(FlowVersionDeploymentAttachment).where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            col(FlowVersionDeploymentAttachment.deployment_id).in_(deployment_ids),
        )
    )

    stmt = delete(Deployment).where(
        Deployment.user_id == user_id,
        col(Deployment.id).in_(deployment_ids),
    )
    result = await db.exec(stmt)
    if result.rowcount is None:
        await logger.aerror(
            "DELETE rowcount was None for deployments=%s -- "
            "database driver may not support rowcount for DELETE statements",
            deployment_ids,
        )
    return int(result.rowcount or 0)
