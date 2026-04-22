"""Deployment sync utilities for provider-backed deployment resources.

Performance note:
These helpers combine expensive DB queries, provider list calls, and
reconciliation deletes. Use them sparingly for best-effort consistency repair
(for example, deployment-guard retries or explicit status refresh), not in
request hot paths.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from itertools import groupby
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger
from lfx.services.adapters.deployment.exceptions import (
    DeploymentServiceError,
    http_status_for_deployment_error,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentListParams,
    DeploymentListResult,
    DeploymentType,
    SnapshotListParams,
    SnapshotListResult,
)
from lfx.services.deps import get_deployment_adapter
from lfx.services.interfaces import DeploymentServiceProtocol

from langflow.services.adapters.deployment.context import deployment_provider_scope
from langflow.services.database.models.deployment.crud import (
    delete_deployments_by_ids,
    list_deployments_for_flows_with_provider_info,
    list_project_deployments_with_provider_info,
)
from langflow.services.database.models.deployment.exceptions import parse_deployment_guard_error
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    delete_deployment_attachments_by_keys,
    delete_orphan_attachments_for_flow_ids,
    delete_orphan_attachments_for_project,
    delete_unbound_attachments,
)
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)
from langflow.services.database.models.flow_version_deployment_attachment.schema import (
    DeploymentAttachmentKey,
    DeploymentAttachmentKeyBatch,
)
from langflow.services.database.utils import require_non_empty

if TYPE_CHECKING:
    from langflow.api.utils import DbSession
    from langflow.services.database.models.deployment.model import Deployment

TGuardOperationResult = TypeVar("TGuardOperationResult")


def extract_verified_snapshot_ids(attachments: list[FlowVersionDeploymentAttachment]) -> list[str]:
    """Return normalized snapshot IDs for attachments, raising on blank values."""
    return [
        require_non_empty(
            att.provider_snapshot_id,
            "FlowVersionDeploymentAttachment.provider_snapshot_id must be non-empty "
            f"(deployment={att.deployment_id}, flow_version={att.flow_version_id})",
        )
        for att in attachments
    ]


def extract_verified_provider_snapshot_ids(snapshot_view: SnapshotListResult) -> set[str]:
    """Return provider snapshot IDs, raising on blank values."""
    error_msg = "Provider returned a snapshot with an empty id."
    return {require_non_empty(str(snapshot.id), error_msg) for snapshot in snapshot_view.snapshots}


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
    except DeploymentServiceError as exc:
        http_status = http_status_for_deployment_error(exc)
        logger.exception("Adapter error (status=%s): %s", http_status, exc.message)
        raise HTTPException(
            status_code=http_status,
            detail=exc.message,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Provider list call failed for provider %s", provider_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while communicating with the deployment provider.",
        ) from exc
    error_msg = "Provider returned a deployment with an empty id."
    known_keys = {require_non_empty(str(item.id), error_msg) for item in provider_view.deployments}
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
    except DeploymentServiceError as exc:
        http_status = http_status_for_deployment_error(exc)
        logger.exception("Adapter error (status=%s): %s", http_status, exc.message)
        raise HTTPException(
            status_code=http_status,
            detail=exc.message,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Provider list_snapshots call failed for provider %s", provider_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while communicating with the deployment provider.",
        ) from exc
    return extract_verified_provider_snapshot_ids(snapshot_view)


async def sync_attachment_snapshot_ids(
    *,
    user_id: UUID,
    attachments: list[FlowVersionDeploymentAttachment],
    known_snapshot_ids: set[str],
    db: DbSession,
) -> dict[UUID, int]:
    """Delete stale attachment rows and return corrected attached counts."""
    corrected_counts: dict[UUID, int] = {}
    stale_attachment_keys: list[DeploymentAttachmentKey] = []
    for attachment in attachments:
        snapshot_id = require_non_empty(
            attachment.provider_snapshot_id,
            "FlowVersionDeploymentAttachment.provider_snapshot_id must be non-empty "
            f"(deployment={attachment.deployment_id}, flow_version={attachment.flow_version_id})",
        )
        if snapshot_id not in known_snapshot_ids:
            await logger.adebug(
                "Snapshot %s for deployment %s not found on provider — marking stale attachment for batch delete",
                snapshot_id,
                attachment.deployment_id,
            )
            stale_attachment_keys.append(
                DeploymentAttachmentKey(
                    deployment_id=attachment.deployment_id,
                    flow_version_id=attachment.flow_version_id,
                )
            )
            continue
        corrected_counts[attachment.deployment_id] = corrected_counts.get(attachment.deployment_id, 0) + 1
    if stale_attachment_keys:
        await delete_deployment_attachments_by_keys(
            db,
            user_id=user_id,
            attachment_key_batch=DeploymentAttachmentKeyBatch(keys=stale_attachment_keys),
        )
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
            await logger.adebug(
                "Provider resource key sync ok (%s): provider=%s, local_deployments=%d, provider_known=%d",
                stale_scope_label,
                provider_account_id,
                len(deployments),
                len(known_resource_keys),
            )

            surviving: list[Deployment] = []
            stale_deployment_ids: list[UUID] = []
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
                stale_deployment_ids.append(deployment.id)
            # TODO: Accumulate stale deployment IDs and orphaned attachment rows across all
            # provider groups and perform a single cross-provider batched delete instead of
            # one batched delete per group, to further reduce round-trips when many provider
            # accounts are involved in a single sync pass. Not done today because buffering
            # every stale resource across the full sync pass can grow unboundedly in memory;
            # any implementation should bound that cost (for example, by flushing in chunks
            # once a size threshold is reached) rather than accumulating without limit.
            if stale_deployment_ids:
                await delete_deployments_by_ids(db, user_id=user_id, deployment_ids=stale_deployment_ids)

            if surviving:
                try:
                    deployment_mapper = get_deployment_mapper(provider_key)
                    bindings = deployment_mapper.extract_snapshot_bindings(provider_view)
                    async with db.begin_nested():
                        await delete_unbound_attachments(
                            db=db,
                            user_id=user_id,
                            provider_account_id=provider_account_id,
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
    """Best-effort sync for one or more flows.

    This path is expensive (cross-table queries + provider round-trips) and
    should remain a narrow repair operation, not a general-purpose read path.
    """
    if not flow_ids:
        return

    deduplicated_flow_ids = list(dict.fromkeys(flow_ids))
    try:
        # Pre-clean known stale local rows (missing deployment parent) so
        # downstream guard retries operate on current, reconcilable state.
        await delete_orphan_attachments_for_flow_ids(
            db=db,
            user_id=user_id,
            flow_ids=deduplicated_flow_ids,
        )
    except Exception:  # noqa: BLE001
        await logger.awarning(
            "Failed to delete orphan deployment attachments before flow sync (flows=%s)",
            deduplicated_flow_ids,
            exc_info=True,
        )

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
    """Best-effort deployment/attachment sync for one flow.

    Intended for targeted status refreshes only; avoid invoking in hot paths.
    """
    try:
        # Keep one-flow status sync resilient to stale legacy attachment rows.
        await delete_orphan_attachments_for_flow_ids(
            db=db,
            user_id=user_id,
            flow_ids=[flow_id],
        )
    except Exception:  # noqa: BLE001
        await logger.awarning(
            "Failed to delete orphan deployment attachments before flow-version sync (flow=%s)",
            flow_id,
            exc_info=True,
        )

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
    """Best-effort deployment/attachment sync for a single project.

    Intended for guard-triggered repair or explicit refresh, not hot paths.
    """
    try:
        # Project-level guard retries can fail repeatedly on stale attachments;
        # prune them before provider reconciliation.
        await delete_orphan_attachments_for_project(
            db=db,
            user_id=user_id,
            project_id=project_id,
        )
    except Exception:  # noqa: BLE001
        await logger.awarning(
            "Failed to delete orphan deployment attachments before project sync (project=%s)",
            project_id,
            exc_info=True,
        )

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


async def retry_flow_operation_on_deployment_guard(
    *,
    db: DbSession,
    user_id: UUID,
    flow_ids: list[UUID] | None = None,
    operation: Callable[[], Awaitable[TGuardOperationResult]],
) -> TGuardOperationResult:
    """Run *operation* and retry once after flow-scoped deployment sync on guard errors.

    Contract:
    The passed ``operation`` must perform guard enforcement itself (for example
    via ORM/service preflight checks that raise ``DeploymentGuardError``) before
    mutating state. This helper does not add guard checks; it only:
    1) detects ``DeploymentGuardError`` failures from the operation,
    2) performs best-effort deployment sync, and
    3) retries the same operation once.
    """
    try:
        async with db.begin_nested():
            return await operation()
    except Exception as exc:
        guard_error = parse_deployment_guard_error(exc)
        if not guard_error:
            raise

    if flow_ids:
        await sync_flow_deployment_state(db=db, flow_ids=flow_ids, user_id=user_id)

    async with db.begin_nested():
        return await operation()


async def retry_project_operation_on_deployment_guard(
    *,
    db: DbSession,
    user_id: UUID,
    project_id: UUID,
    operation: Callable[[], Awaitable[TGuardOperationResult]],
) -> TGuardOperationResult:
    """Run *operation* and retry once after project-scoped deployment sync on guard errors.

    Contract:
    The passed ``operation`` must perform guard enforcement itself (for example
    via ORM/service preflight checks that raise ``DeploymentGuardError``) before
    mutating state. This helper does not add project guards; it only:
    1) detects ``DeploymentGuardError`` failures from the operation,
    2) performs best-effort project deployment sync, and
    3) retries the same operation once.
    """
    try:
        async with db.begin_nested():
            return await operation()
    except Exception as exc:
        guard_error = parse_deployment_guard_error(exc)
        if not guard_error:
            raise

    await sync_project_deployments(db=db, project_id=project_id, user_id=user_id)

    async with db.begin_nested():
        return await operation()
