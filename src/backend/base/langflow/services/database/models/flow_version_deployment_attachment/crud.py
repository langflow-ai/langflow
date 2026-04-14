from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select, update

from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow_version.model import FlowVersion


class AttachmentConflictError(ValueError):
    """Base exception for flow-version attachment conflicts."""


class SnapshotFlowVersionConflictError(AttachmentConflictError):
    """Raised when one provider snapshot is linked to multiple flow versions."""


class DeploymentAttachmentConflictError(AttachmentConflictError):
    """Raised when a deployment attachment violates DB uniqueness constraints."""


async def _check_snapshot_flow_version_conflict(
    db: AsyncSession,
    *,
    provider_snapshot_id: str | None,
    flow_version_id: UUID,
) -> None:
    """Ensure a provider_snapshot_id is only ever linked to one flow version.

    A tool can appear in multiple deployments, but every row with the same
    provider_snapshot_id must point to the same flow_version_id.  For example:

        (FV=1, tool=A, deploy=X)  ✓  — first use of tool A
        (FV=1, tool=A, deploy=Y)  ✓  — same FV, different deployment, OK
        (FV=2, tool=A, deploy=Z)  ✗  — different FV for tool A, rejected

    This cannot be expressed as a DB unique constraint, so we enforce it here.

    Concurrency note: this is a read-before-write guard with no DB-level lock
    or uniqueness guarantee on provider_snapshot_id. Concurrent transactions
    can still both pass this check before either commit.
    """
    if not provider_snapshot_id:
        return
    stmt = (
        select(FlowVersionDeploymentAttachment.flow_version_id)
        .where(
            FlowVersionDeploymentAttachment.provider_snapshot_id == provider_snapshot_id,
            FlowVersionDeploymentAttachment.flow_version_id != flow_version_id,
        )
        .limit(1)
    )
    conflict = (await db.exec(stmt)).first()
    if conflict is not None:
        logger.info(
            "Snapshot flow-version conflict detected for provider_snapshot_id=%s (requested=%s existing=%s).",
            provider_snapshot_id,
            flow_version_id,
            conflict,
        )
        msg = (
            f"Tool '{provider_snapshot_id}' is already attached to a different flow version. "
            f"Each tool can only be linked to one flow version."
        )
        raise SnapshotFlowVersionConflictError(msg)


async def create_deployment_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_version_id: UUID,
    deployment_id: UUID,
    provider_snapshot_id: str | None = None,
) -> FlowVersionDeploymentAttachment:
    await _check_snapshot_flow_version_conflict(
        db,
        provider_snapshot_id=provider_snapshot_id,
        flow_version_id=flow_version_id,
    )
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
            f"Attachment conflicts with an existing record (flow_version={flow_version_id}, deployment={deployment_id})"
        )
        raise DeploymentAttachmentConflictError(msg) from exc
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
    flow_ids: list[UUID] | None = None,
) -> list[FlowVersionDeploymentAttachment]:
    stmt = select(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.deployment_id == deployment_id,
    )
    if flow_ids:
        from langflow.services.database.models.flow_version.model import FlowVersion

        stmt = stmt.join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id).where(
            col(FlowVersion.flow_id).in_(flow_ids),
        )
    stmt = stmt.order_by(FlowVersionDeploymentAttachment.created_at)
    return list((await db.exec(stmt)).all())


async def list_deployment_attachments_with_versions(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
    offset: int,
    limit: int,
    flow_ids: list[UUID] | None = None,
) -> list[tuple[FlowVersionDeploymentAttachment, FlowVersion, str | None]]:
    """Return paginated attachment rows joined with version metadata and flow name."""
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion

    if limit <= 0:
        return []

    stmt = (
        select(FlowVersionDeploymentAttachment, FlowVersion, col(Flow.name).label("flow_name"))
        .join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id)
        .join(Flow, Flow.id == FlowVersion.flow_id)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.deployment_id == deployment_id,
        )
    )
    if flow_ids:
        stmt = stmt.where(col(FlowVersion.flow_id).in_(flow_ids))
    stmt = (
        stmt.order_by(
            col(FlowVersionDeploymentAttachment.created_at).desc(),
            col(FlowVersionDeploymentAttachment.updated_at).desc(),
        )
        .offset(offset)
        .limit(limit)
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
        col(FlowVersionDeploymentAttachment.flow_version_id).in_(flow_version_ids),
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
    await _check_snapshot_flow_version_conflict(
        db,
        provider_snapshot_id=provider_snapshot_id,
        flow_version_id=attachment.flow_version_id,
    )
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


async def list_attachments_by_deployment_ids(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_ids: list[UUID],
) -> list[FlowVersionDeploymentAttachment]:
    if not deployment_ids:
        return []
    stmt = (
        select(FlowVersionDeploymentAttachment)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            col(FlowVersionDeploymentAttachment.deployment_id).in_(deployment_ids),
        )
        .order_by(FlowVersionDeploymentAttachment.created_at)
    )
    return list((await db.exec(stmt)).all())


async def list_attachments_for_flow_with_provider_info(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_id: UUID,
) -> list[tuple[FlowVersionDeploymentAttachment, UUID, str]]:
    """Return attachments for all versions of a flow, with provider context.

    Each tuple contains:
      - the attachment row
      - the deployment's ``deployment_provider_account_id``
      - the provider account's ``provider_key``

    This avoids N+1 queries when the caller needs to group attachments by
    provider for sync operations.
    """
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.flow_version.model import FlowVersion

    stmt = (
        select(
            FlowVersionDeploymentAttachment,
            Deployment.deployment_provider_account_id,
            DeploymentProviderAccount.provider_key,
        )
        .join(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
        .join(DeploymentProviderAccount, DeploymentProviderAccount.id == Deployment.deployment_provider_account_id)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            col(FlowVersionDeploymentAttachment.flow_version_id).in_(
                select(FlowVersion.id).where(FlowVersion.flow_id == flow_id)
            ),
        )
        .order_by(FlowVersionDeploymentAttachment.created_at)
    )
    rows = (await db.exec(stmt)).all()
    return [(attachment, provider_account_id, provider_key) for attachment, provider_account_id, provider_key in rows]


async def list_attachments_for_flow_with_deployment_info(
    db: AsyncSession,
    *,
    user_id: UUID,
    flow_id: UUID,
) -> list[tuple[FlowVersionDeploymentAttachment, str, str, str]]:
    """Return deployed attachments for all versions of a flow, with deployment context.

    Each tuple contains:
      - the attachment row
      - the deployment's ``name``
      - the deployment's ``deployment_type`` value
      - the provider account's ``provider_key``

    Only attachments with a non-null ``provider_snapshot_id`` are returned
    (i.e. those that have actually been materialized on the provider).
    Results are ordered by ``updated_at`` descending so the most recent
    attachment per deployment comes first.
    """
    from langflow.services.database.models.deployment.model import Deployment
    from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
    from langflow.services.database.models.flow_version.model import FlowVersion

    stmt = (
        select(
            FlowVersionDeploymentAttachment,
            Deployment.name,
            Deployment.deployment_type,
            DeploymentProviderAccount.provider_key,
        )
        .join(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
        .join(DeploymentProviderAccount, DeploymentProviderAccount.id == Deployment.deployment_provider_account_id)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.provider_snapshot_id.is_not(None),  # type: ignore[union-attr]
            col(FlowVersionDeploymentAttachment.flow_version_id).in_(
                select(FlowVersion.id).where(FlowVersion.flow_id == flow_id)
            ),
        )
        .order_by(FlowVersionDeploymentAttachment.updated_at.desc())  # type: ignore[union-attr]
    )
    rows = (await db.exec(stmt)).all()
    return [(att, name, dtype.value, pkey) for att, name, dtype, pkey in rows]


async def get_attachment_by_provider_snapshot_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_snapshot_id: str,
) -> FlowVersionDeploymentAttachment | None:
    """Look up an attachment by its provider_snapshot_id.

    Used by the PATCH /snapshots/{provider_snapshot_id} endpoint to
    resolve the deployment context for a provider-owned snapshot.
    """
    stmt = select(FlowVersionDeploymentAttachment).where(
        FlowVersionDeploymentAttachment.user_id == user_id,
        FlowVersionDeploymentAttachment.provider_snapshot_id == provider_snapshot_id,
    )
    return (await db.exec(stmt)).first()


async def update_flow_version_by_provider_snapshot_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider_snapshot_id: str,
    flow_version_id: UUID,
) -> int:
    """Update all attachment rows that share a provider_snapshot_id.

    A single provider snapshot can be attached to multiple deployments, so
    route handlers must update every matching row together.

    Concurrency note: this is a set-based UPDATE without an explicit lock/read
    phase. If concurrent writers touch the same snapshot id, last commit wins.
    """
    stmt = (
        update(FlowVersionDeploymentAttachment)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.provider_snapshot_id == provider_snapshot_id,
        )
        .values(flow_version_id=flow_version_id)
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
            col(FlowVersionDeploymentAttachment.deployment_id).in_(deployment_ids),
        )
        .group_by(FlowVersionDeploymentAttachment.deployment_id)
    )
    rows = (await db.exec(stmt)).all()
    return {deployment_id: int(count) for deployment_id, count in rows}


async def count_deployment_attachments(
    db: AsyncSession,
    *,
    user_id: UUID,
    deployment_id: UUID,
    flow_ids: list[UUID] | None = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(FlowVersionDeploymentAttachment)
        .where(
            FlowVersionDeploymentAttachment.user_id == user_id,
            FlowVersionDeploymentAttachment.deployment_id == deployment_id,
        )
    )
    if flow_ids:
        from langflow.services.database.models.flow_version.model import FlowVersion

        stmt = stmt.join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id).where(
            col(FlowVersion.flow_id).in_(flow_ids),
        )
    total = (await db.exec(stmt)).one()
    return int(total or 0)
