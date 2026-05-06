from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    get_friendly_guard_detail,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.model import (
    FlowVersionDeploymentAttachment,
)

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.adapters.deployment.schema import DeploymentType
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.deployment_provider_account.schemas import DeploymentProviderKey


def _raise_flow_deployed_in_project() -> None:
    raise DeploymentGuardError(
        code="FLOW_DEPLOYED_IN_PROJECT",
        technical_detail=(
            "UPDATE flow.folder_id blocked: versions of this flow remain attached "
            "to deployments in the current project scope."
        ),
        detail=get_friendly_guard_detail("FLOW_DEPLOYED_IN_PROJECT"),
    )


async def ensure_flow_move_allowed(
    db: AsyncSession,
    *,
    flow_id: UUID,
    old_folder_id: UUID | None,
    new_folder_id: UUID | None,
) -> None:
    """Block moving a deployed flow out of its current project scope."""
    if old_folder_id == new_folder_id:
        return

    attached_in_old_project = (
        await db.exec(
            select(FlowVersionDeploymentAttachment.id)
            .join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id)
            .join(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
            .where(
                FlowVersion.flow_id == flow_id,
                Deployment.project_id == old_folder_id,
            )
            .limit(1)
        )
    ).first()
    if attached_in_old_project is None:
        return

    _raise_flow_deployed_in_project()


async def ensure_flow_moves_allowed(
    db: AsyncSession,
    *,
    flow_folder_pairs: list[tuple[UUID, UUID | None]],
    new_folder_id: UUID | None,
) -> None:
    """Validate a batch of flow folder moves before a bulk update.

    Groups flows by source folder and issues one query per group,
    so the typical single-source-folder case runs a single SELECT.
    """
    candidates = [(fid, ofid) for fid, ofid in flow_folder_pairs if ofid != new_folder_id]
    if not candidates:
        return

    by_folder: dict[UUID | None, list[UUID]] = {}
    for flow_id, old_folder_id in candidates:
        by_folder.setdefault(old_folder_id, []).append(flow_id)

    for old_folder_id, flow_ids in by_folder.items():
        blocked = (
            await db.exec(
                select(FlowVersion.flow_id)
                .join(
                    FlowVersionDeploymentAttachment,
                    FlowVersionDeploymentAttachment.flow_version_id == FlowVersion.id,
                )
                .join(Deployment, Deployment.id == FlowVersionDeploymentAttachment.deployment_id)
                .where(
                    col(FlowVersion.flow_id).in_(flow_ids),
                    Deployment.project_id == old_folder_id,
                )
                .limit(1)
            )
        ).first()
        if blocked is not None:
            _raise_flow_deployed_in_project()


def ensure_deployment_immutable_fields(
    *,
    old_project_id: UUID,
    new_project_id: UUID,
    old_deployment_type: DeploymentType,
    new_deployment_type: DeploymentType,
    old_resource_key: str,
    new_resource_key: str,
    old_provider_account_id: UUID,
    new_provider_account_id: UUID,
) -> None:
    """Block immutable deployment identity/scope field updates."""
    if old_project_id != new_project_id:
        raise DeploymentGuardError(
            code="DEPLOYMENT_PROJECT_MOVE",
            technical_detail=(
                "UPDATE deployment.project_id blocked: project scope is immutable for existing deployments."
            ),
            detail=get_friendly_guard_detail("DEPLOYMENT_PROJECT_MOVE"),
        )

    if old_deployment_type != new_deployment_type:
        raise DeploymentGuardError(
            code="DEPLOYMENT_TYPE_UPDATE",
            technical_detail="Cannot modify deployment type on an existing deployment.",
            detail=get_friendly_guard_detail("DEPLOYMENT_TYPE_UPDATE"),
        )

    if old_resource_key != new_resource_key:
        raise DeploymentGuardError(
            code="DEPLOYMENT_RESOURCE_KEY_UPDATE",
            technical_detail="Cannot modify deployment resource key on an existing deployment.",
            detail=get_friendly_guard_detail("DEPLOYMENT_RESOURCE_KEY_UPDATE"),
        )

    if old_provider_account_id != new_provider_account_id:
        raise DeploymentGuardError(
            code="DEPLOYMENT_PROVIDER_ACCOUNT_MOVE",
            technical_detail=(
                "UPDATE deployment.deployment_provider_account_id blocked: provider account scope is immutable."
            ),
            detail=get_friendly_guard_detail("DEPLOYMENT_PROVIDER_ACCOUNT_MOVE"),
        )


def ensure_provider_account_identity_immutable(
    *,
    old_provider_key: DeploymentProviderKey,
    new_provider_key: DeploymentProviderKey,
    old_provider_tenant_id: str | None,
    new_provider_tenant_id: str | None,
    old_provider_url: str,
    new_provider_url: str,
) -> None:
    """Block updates to immutable deployment provider account identity fields."""
    if (
        old_provider_key == new_provider_key
        and old_provider_tenant_id == new_provider_tenant_id
        and old_provider_url == new_provider_url
    ):
        return

    raise DeploymentGuardError(
        code="DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE",
        technical_detail=(
            "UPDATE deployment_provider_account blocked: provider_key, provider_tenant_id, "
            "and provider_url are immutable."
        ),
        detail=get_friendly_guard_detail("DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE"),
    )


async def ensure_attachment_project_match(
    db: AsyncSession,
    *,
    flow_version_id: UUID,
    deployment_id: UUID,
) -> None:
    """Block cross-project flow-version deployment attachments.

    Note:
        This guard compares project scopes only. If both lookups resolve to
        ``None`` (for example, both records are missing), the equality check
        passes and this guard returns. Entity existence is still enforced by
        downstream FK/constraint checks on flush/commit.
    """
    flow_project_id = (
        await db.exec(
            select(Flow.folder_id)
            .select_from(FlowVersion)
            .join(Flow, Flow.id == FlowVersion.flow_id)
            .where(FlowVersion.id == flow_version_id)
            .limit(1)
        )
    ).first()
    deployment_project_id = (
        await db.exec(select(Deployment.project_id).where(Deployment.id == deployment_id).limit(1))
    ).first()

    if flow_project_id == deployment_project_id:
        return

    raise DeploymentGuardError(
        code="CROSS_PROJECT_ATTACHMENT",
        technical_detail=(
            "INSERT flow_version_deployment_attachment blocked: flow project scope does not match "
            "deployment project scope."
        ),
        detail=get_friendly_guard_detail("CROSS_PROJECT_ATTACHMENT"),
    )
