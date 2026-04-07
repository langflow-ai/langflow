"""Deployment sync utilities for provider-backed deployment resources."""

from __future__ import annotations

from collections import defaultdict
from itertools import groupby
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger
from lfx.services.adapters.deployment.schema import DeploymentListParams, DeploymentType, SnapshotListParams
from lfx.services.deps import get_deployment_adapter
from lfx.services.interfaces import DeploymentServiceProtocol

from langflow.services.adapters.deployment.context import deployment_provider_scope
from langflow.services.database.models.deployment.crud import (
    delete_deployment_by_id,
    list_deployments_for_flows_with_provider_info,
    list_project_deployments_with_provider_info,
)
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    delete_deployment_attachment,
    list_attachments_for_flow_with_provider_info,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)

if TYPE_CHECKING:
    from langflow.api.utils import DbSession
    from langflow.services.database.models.deployment.model import Deployment

    from .base import BaseDeploymentMapper


async def fetch_provider_resource_keys(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    resource_keys: list[str],
    deployment_type: DeploymentType | None = None,
) -> set[str]:
    """Ask the provider which *resource_keys* it recognises."""
    if not resource_keys:
        return set()
    try:
        provider_view = await deployment_adapter.list(
            user_id=user_id,
            db=db,
            params=DeploymentListParams(
                deployment_types=[deployment_type] if deployment_type is not None else None,
                deployment_ids=resource_keys,
            ),
        )
    except Exception as exc:
        logger.exception(
            "Provider list call failed for provider %s",
            provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list deployments from provider: {exc}",
        ) from exc
    return {str(item.id) for item in provider_view.deployments if item.id}


async def fetch_provider_snapshot_keys(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    snapshot_ids: list[str],
) -> set[str]:
    """Ask the provider which *snapshot_ids* it recognises."""
    if not snapshot_ids:
        return set()
    try:
        snapshot_view = await deployment_adapter.list_snapshots(
            user_id=user_id,
            db=db,
            params=SnapshotListParams(snapshot_ids=snapshot_ids),
        )
    except Exception as exc:
        logger.exception(
            "Provider list_snapshots call failed for provider %s",
            provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to list snapshots from provider: {exc}",
        ) from exc
    return {str(item.id) for item in snapshot_view.snapshots if item.id}


async def sync_attachment_snapshot_ids(
    *,
    user_id: UUID,
    deployment_ids: list[UUID],
    attachments: list[FlowVersionDeploymentAttachment],
    known_snapshot_ids: set[str],
    db: DbSession,
) -> dict[UUID, int]:
    """Delete stale attachment rows and return corrected attached counts."""
    corrected_counts: dict[UUID, int] = dict.fromkeys(deployment_ids, 0)
    for attachment in attachments:
        snapshot_id = (attachment.provider_snapshot_id or "").strip()
        if snapshot_id and snapshot_id not in known_snapshot_ids:
            logger.warning(
                "Snapshot %s for deployment %s not found on provider — deleting stale attachment",
                snapshot_id,
                attachment.deployment_id,
            )
            await delete_deployment_attachment(
                db,
                user_id=user_id,
                flow_version_id=attachment.flow_version_id,
                deployment_id=attachment.deployment_id,
            )
        else:
            corrected_counts[attachment.deployment_id] = corrected_counts.get(attachment.deployment_id, 0) + 1
    return corrected_counts


async def sync_provider_attachment_snapshots(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    deployment_mapper: BaseDeploymentMapper,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    attachments: list[FlowVersionDeploymentAttachment],
    deployment_ids: list[UUID] | None = None,
) -> dict[UUID, int] | None:
    """Validate attachment snapshot IDs against the provider inside a savepoint."""
    snapshot_ids = list(dict.fromkeys(deployment_mapper.util_snapshot_ids_to_verify(attachments)))
    if not snapshot_ids:
        return None

    known_snapshots = await fetch_provider_snapshot_keys(
        deployment_adapter=deployment_adapter,
        user_id=user_id,
        provider_id=provider_id,
        db=db,
        snapshot_ids=snapshot_ids,
    )
    if deployment_ids is None:
        deployment_ids = list(dict.fromkeys(attachment.deployment_id for attachment in attachments))

    async with db.begin_nested():
        return await sync_attachment_snapshot_ids(
            user_id=user_id,
            deployment_ids=deployment_ids,
            attachments=attachments,
            known_snapshot_ids=known_snapshots,
            db=db,
        )


async def sync_flow_version_attachments(
    *,
    db: DbSession,
    flow_id: UUID,
    user_id: UUID,
) -> None:
    """Best-effort snapshot sync for all attachments of a flow's versions."""
    from langflow.api.v1.mappers.deployments.registry import get_deployment_mapper

    rows = await list_attachments_for_flow_with_provider_info(db, user_id=user_id, flow_ids=[flow_id])
    if not rows:
        return

    grouped: dict[tuple[UUID, str], list[FlowVersionDeploymentAttachment]] = defaultdict(list)
    for attachment, provider_account_id, provider_key in rows:
        grouped[(provider_account_id, provider_key)].append(attachment)

    for (provider_account_id, provider_key), attachments in grouped.items():
        try:
            deployment_adapter = get_deployment_adapter(provider_key)
            deployment_mapper = get_deployment_mapper(provider_key)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to resolve adapter/mapper for provider_key=%s during flow version sync; skipping",
                provider_key,
                exc_info=True,
            )
            continue

        try:
            with deployment_provider_scope(provider_account_id):
                await sync_provider_attachment_snapshots(
                    deployment_adapter=deployment_adapter,
                    deployment_mapper=deployment_mapper,
                    user_id=user_id,
                    provider_id=provider_account_id,
                    db=db,
                    attachments=attachments,
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for provider %s (flow %s); skipping",
                provider_account_id,
                flow_id,
                exc_info=True,
            )


async def _cleanup_stale_deployments_by_provider(
    *,
    db: DbSession,
    user_id: UUID,
    deployments_with_provider: list[tuple[Deployment, str]],
    stale_scope_label: str,
    failure_log_message: str,
    failure_scope_value: UUID | list[UUID],
) -> None:
    for (provider_account_id, provider_key), grouped_items in groupby(
        deployments_with_provider,
        key=lambda item: (item[0].deployment_provider_account_id, item[1]),
    ):
        deployments = [deployment for deployment, _provider_key in grouped_items]
        try:
            deployment_adapter = get_deployment_adapter(provider_key)
            with deployment_provider_scope(provider_account_id):
                known_resource_keys = await fetch_provider_resource_keys(
                    deployment_adapter=deployment_adapter,
                    user_id=user_id,
                    provider_id=provider_account_id,
                    db=db,
                    resource_keys=[deployment.resource_key for deployment in deployments],
                )

            for deployment in deployments:
                if deployment.resource_key in known_resource_keys:
                    continue
                await logger.awarning(
                    "Deployment %s (resource_key=%s) is stale during %s sync; deleting local row",
                    deployment.id,
                    deployment.resource_key,
                    stale_scope_label,
                )
                await delete_deployment_by_id(db, user_id=user_id, deployment_id=deployment.id)
        except Exception:  # noqa: BLE001
            await logger.awarning(
                failure_log_message,
                provider_account_id,
                failure_scope_value,
                exc_info=True,
            )


async def sync_flow_deployment_state(
    *,
    db: DbSession,
    flow_ids: list[UUID],
    user_id: UUID,
) -> None:
    """Best-effort deployment and snapshot sync for one or more flows."""
    from langflow.api.v1.mappers.deployments.registry import get_deployment_mapper

    if not flow_ids:
        return

    deduplicated_flow_ids = list(dict.fromkeys(flow_ids))
    deployments_with_provider = await list_deployments_for_flows_with_provider_info(
        db,
        user_id=user_id,
        flow_ids=deduplicated_flow_ids,
    )
    if not deployments_with_provider:
        return

    await _cleanup_stale_deployments_by_provider(
        db=db,
        user_id=user_id,
        deployments_with_provider=deployments_with_provider,
        stale_scope_label="flow",
        failure_log_message="Deployment-level flow sync failed for provider %s (flows=%s); continuing without sync",
        failure_scope_value=deduplicated_flow_ids,
    )

    rows_after_deployment_sync = await list_attachments_for_flow_with_provider_info(
        db, user_id=user_id, flow_ids=deduplicated_flow_ids
    )
    if not rows_after_deployment_sync:
        return

    attachments_grouped_by_provider: dict[tuple[UUID, str], list[FlowVersionDeploymentAttachment]] = defaultdict(list)
    for attachment, provider_account_id, provider_key in rows_after_deployment_sync:
        attachments_grouped_by_provider[(provider_account_id, provider_key)].append(attachment)

    for (provider_account_id, provider_key), attachments in attachments_grouped_by_provider.items():
        try:
            deployment_adapter = get_deployment_adapter(provider_key)
            deployment_mapper = get_deployment_mapper(provider_key)
            snapshot_ids = list(dict.fromkeys(deployment_mapper.util_snapshot_ids_to_verify(attachments)))
            if not snapshot_ids:
                continue

            with deployment_provider_scope(provider_account_id):
                known_snapshot_ids = await fetch_provider_snapshot_keys(
                    deployment_adapter=deployment_adapter,
                    user_id=user_id,
                    provider_id=provider_account_id,
                    db=db,
                    snapshot_ids=snapshot_ids,
                )

            async with db.begin_nested():
                await sync_attachment_snapshot_ids(
                    user_id=user_id,
                    deployment_ids=list({attachment.deployment_id for attachment in attachments}),
                    attachments=attachments,
                    known_snapshot_ids=known_snapshot_ids,
                    db=db,
                )
        except Exception:  # noqa: BLE001
            await logger.awarning(
                "Snapshot-level flow sync failed for provider %s (flows=%s); continuing without sync",
                provider_account_id,
                deduplicated_flow_ids,
                exc_info=True,
            )


async def sync_project_deployments(
    *,
    db: DbSession,
    project_id: UUID,
    user_id: UUID,
) -> None:
    """Best-effort deployment-level sync for a single project."""
    rows = await list_project_deployments_with_provider_info(db, user_id=user_id, project_id=project_id)
    if not rows:
        return

    await _cleanup_stale_deployments_by_provider(
        db=db,
        user_id=user_id,
        deployments_with_provider=rows,
        stale_scope_label="project",
        failure_log_message="Project deployment sync failed for provider %s (project=%s); continuing without sync",
        failure_scope_value=project_id,
    )
