"""Deployment sync utilities for provider-backed deployment resources."""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger
from lfx.services.adapters.deployment.schema import (
    DeploymentListParams,
    DeploymentListResult,
    DeploymentType,
    SnapshotListParams,
)
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
    delete_unbound_attachments,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)

if TYPE_CHECKING:
    from langflow.api.utils import DbSession
    from langflow.services.database.models.deployment.model import Deployment


async def fetch_provider_resource_keys(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    resource_keys: list[str],
    deployment_type: DeploymentType | None = None,
) -> tuple[set[str], DeploymentListResult]:
    """Ask the provider which *resource_keys* it recognises.

    Returns:
        tuple[set[str], DeploymentListResult]:
            - known_resource_keys: all provider-recognized deployment IDs from
              the response (`str(item.id)`), used for stale deployment pruning.
            - provider_view: the full provider list payload for the same query,
              used by mapper-specific binding extraction.
    """
    if not resource_keys:
        return set(), DeploymentListResult(deployments=[])
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
    known_keys = {str(item.id) for item in provider_view.deployments if item.id}
    return known_keys, provider_view


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


async def _sync_deployments_and_attachments_by_provider(
    *,
    db: DbSession,
    user_id: UUID,
    deployments_with_provider: list[tuple[Deployment, str]],
    stale_scope_label: str,
    failure_log_message: str,
    failure_scope_value: UUID | list[UUID],
) -> None:
    from langflow.api.v1.mappers.deployments.registry import get_deployment_mapper

    grouped_source = sorted(
        deployments_with_provider,
        key=lambda item: (item[0].deployment_provider_account_id, item[1], item[0].id),
    )

    for (provider_account_id, provider_key), grouped_items in groupby(
        grouped_source,
        key=lambda item: (item[0].deployment_provider_account_id, item[1]),
    ):
        deployments = [deployment for deployment, _provider_key in grouped_items]
        try:
            deployment_adapter = get_deployment_adapter(provider_key)
            with deployment_provider_scope(provider_account_id):
                known_resource_keys, provider_view = await fetch_provider_resource_keys(
                    deployment_adapter=deployment_adapter,
                    user_id=user_id,
                    provider_id=provider_account_id,
                    db=db,
                    resource_keys=[deployment.resource_key for deployment in deployments],
                )

            surviving: list[Deployment] = []
            for deployment in deployments:
                if deployment.resource_key in known_resource_keys:
                    surviving.append(deployment)
                    continue
                await logger.awarning(
                    "Deployment %s (resource_key=%s) is stale during %s sync; deleting local row",
                    deployment.id,
                    deployment.resource_key,
                    stale_scope_label,
                )
                await delete_deployment_by_id(db, user_id=user_id, deployment_id=deployment.id)

            if surviving:
                try:
                    deployment_mapper = get_deployment_mapper(provider_key)
                    bindings = deployment_mapper.extract_snapshot_bindings(provider_view)
                    async with db.begin_nested():
                        await delete_unbound_attachments(
                            db=db,
                            user_id=user_id,
                            deployment_ids=[deployment.id for deployment in surviving],
                            bindings=bindings,
                        )
                except Exception:  # noqa: BLE001
                    await logger.awarning(
                        "Attachment binding sync failed for provider %s (%s); continuing",
                        provider_account_id,
                        stale_scope_label,
                        exc_info=True,
                    )
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
    deployment_provider_account_id: UUID | None = None,
) -> None:
    """Best-effort deployment and attachment binding sync for one or more flows."""
    if not flow_ids:
        return

    deduplicated_flow_ids = list(dict.fromkeys(flow_ids))
    deployments_with_provider = await list_deployments_for_flows_with_provider_info(
        db,
        user_id=user_id,
        flow_ids=deduplicated_flow_ids,
        provider_account_id=deployment_provider_account_id,
    )
    if not deployments_with_provider:
        return

    await _sync_deployments_and_attachments_by_provider(
        db=db,
        user_id=user_id,
        deployments_with_provider=deployments_with_provider,
        stale_scope_label="flow",
        failure_log_message="Deployment-level flow sync failed for provider %s (flows=%s); continuing without sync",
        failure_scope_value=deduplicated_flow_ids,
    )


async def sync_flow_version_attachments(
    *,
    db: DbSession,
    flow_id: UUID,
    user_id: UUID,
    deployment_provider_account_id: UUID | None = None,
) -> None:
    """Best-effort deployment and attachment binding sync for one flow."""
    deployments_with_provider = await list_deployments_for_flows_with_provider_info(
        db,
        user_id=user_id,
        flow_ids=[flow_id],
        provider_account_id=deployment_provider_account_id,
    )
    if not deployments_with_provider:
        return

    await _sync_deployments_and_attachments_by_provider(
        db=db,
        user_id=user_id,
        deployments_with_provider=deployments_with_provider,
        stale_scope_label="flow_version",
        failure_log_message="Flow version sync failed for provider %s (flow=%s); skipping",
        failure_scope_value=flow_id,
    )


async def sync_project_deployments(
    *,
    db: DbSession,
    project_id: UUID,
    user_id: UUID,
    deployment_provider_account_id: UUID | None = None,
) -> None:
    """Best-effort deployment and attachment binding sync for a single project."""
    rows = await list_project_deployments_with_provider_info(
        db,
        user_id=user_id,
        project_id=project_id,
        provider_account_id=deployment_provider_account_id,
    )
    if not rows:
        return

    await _sync_deployments_and_attachments_by_provider(
        db=db,
        user_id=user_id,
        deployments_with_provider=rows,
        stale_scope_label="project",
        failure_log_message="Project deployment sync failed for provider %s (project=%s); continuing without sync",
        failure_scope_value=project_id,
    )
