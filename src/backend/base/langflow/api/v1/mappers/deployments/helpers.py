"""Shared mapper helpers for deployment flow-version resolution and route utilities."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import HTTPException, Query, status
from fastapi_pagination import Params
from lfx.log.logger import logger
from lfx.services.adapters.deployment.exceptions import (
    DeploymentServiceError,
    ResourceConflictError,
    http_status_for_deployment_error,
)
from lfx.services.adapters.deployment.schema import (
    BaseFlowArtifact,
    DeploymentType,
    DeploymentUpdateResult,
    SnapshotListParams,
    SnapshotListResult,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentCreateResult as AdapterDeploymentCreateResult,
)
from lfx.services.deps import get_deployment_adapter
from lfx.services.interfaces import DeploymentServiceProtocol
from sqlalchemy import and_, literal, union_all
from sqlmodel import col, func, select

from langflow.api.v1.mappers.deployments.contracts import ProviderSnapshotBinding
from langflow.api.v1.mappers.deployments.sync import (
    extract_verified_provider_snapshot_ids,
    extract_verified_snapshot_ids,
    fetch_provider_resource_keys,
    sync_attachment_snapshot_ids,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
)
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.adapters.deployment.context import deployment_provider_scope
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    delete_deployment_by_id,
    list_deployments_page,
)
from langflow.services.database.models.deployment.crud import (
    get_deployment as get_deployment_db,
)
from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.deployment_provider_account.crud import (
    get_provider_account_by_id as get_provider_account_row_by_id,
)
from langflow.services.database.models.deployment_provider_account.model import DeploymentProviderAccount
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    count_attachments_by_deployment_ids,
    count_deployment_attachments,
    create_deployment_attachment,
    delete_deployment_attachment,
    delete_unbound_attachments,
    get_deployment_attachment,
    list_deployment_attachments,
    list_deployment_attachments_with_versions,
    update_deployment_attachment_provider_snapshot_id,
)
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.utils import require_non_empty

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langflow.api.utils import DbSession
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )

    from .base import BaseDeploymentMapper


def parse_flow_version_reference_ids(reference_ids: Sequence[UUID | str]) -> list[UUID]:
    """Normalize UUID/string references into validated flow-version UUIDs."""
    flow_version_ids: list[UUID] = []
    for flow_version_ref in reference_ids:
        if isinstance(flow_version_ref, UUID):
            flow_version_ids.append(flow_version_ref)
            continue
        flow_version_ref_str = str(flow_version_ref).strip()
        try:
            flow_version_ids.append(UUID(flow_version_ref_str))
        except ValueError as exc:
            msg = f"Invalid flow version id: {flow_version_ref}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg) from exc
    return flow_version_ids


def _build_indexed_flow_version_ids_cte(*, flow_version_ids: list[UUID]):
    indexed_selects = [
        select(literal(index).label("position"), literal(flow_version_id).label("flow_version_id"))
        for index, flow_version_id in enumerate(flow_version_ids)
    ]
    return (indexed_selects[0] if len(indexed_selects) == 1 else union_all(*indexed_selects)).cte(
        "indexed_flow_version_ids"
    )


async def build_flow_artifacts_from_flow_versions(
    *,
    db,
    user_id: UUID,
    deployment_db_id: UUID,
    flow_version_ids: list[UUID],
) -> list[tuple[UUID, int, UUID, BaseFlowArtifact]]:
    """Resolve deployment-scoped flow version ids into artifacts preserving input order."""
    if not flow_version_ids:
        return []

    indexed_flow_version_ids_cte = _build_indexed_flow_version_ids_cte(flow_version_ids=flow_version_ids)

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            col(FlowVersion.id).label("flow_version_id"),
            col(FlowVersion.data).label("flow_version_data"),
            col(FlowVersion.version_number).label("flow_version_number"),
            col(Flow.folder_id).label("project_id"),
            col(Flow.id).label("flow_id"),
            col(Flow.name).label("flow_name"),
            col(Flow.description).label("flow_description"),
            col(Flow.tags).label("flow_tags"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(
            FlowVersion,
            and_(
                FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id,
                FlowVersion.user_id == user_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowVersion.flow_id,
                Flow.user_id == user_id,
            ),
        )
        .join(
            Deployment,
            and_(
                Deployment.id == deployment_db_id,
                Deployment.user_id == user_id,
                Deployment.project_id == Flow.folder_id,
            ),
        )
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = (
            "One or more flow versions are invalid. "
            "Please ensure the flows belong to the project containing the deployment."
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    artifacts: list[tuple[UUID, int, UUID, BaseFlowArtifact]] = []
    for row in rows:
        if row.flow_version_data is None:
            msg = f"Flow version {row.flow_version_id} has no data (snapshot may be corrupted)."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        artifacts.append(
            (
                row.flow_version_id,
                row.flow_version_number,
                row.project_id,
                BaseFlowArtifact(
                    id=row.flow_id,
                    name=row.flow_name,
                    description=row.flow_description,
                    data=row.flow_version_data,
                    tags=row.flow_tags,
                ),
            )
        )
    return artifacts


async def build_project_scoped_flow_artifacts_from_flow_versions(
    *,
    db,
    user_id: UUID,
    project_id: UUID,
    reference_ids: Sequence[UUID | str],
) -> list[tuple[UUID, BaseFlowArtifact]]:
    """Resolve project-scoped flow version references preserving input order."""
    flow_version_ids = parse_flow_version_reference_ids(reference_ids)
    if not flow_version_ids:
        return []
    indexed_flow_version_ids_cte = _build_indexed_flow_version_ids_cte(flow_version_ids=flow_version_ids)

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            col(FlowVersion.id).label("flow_version_id"),
            col(FlowVersion.data).label("flow_version_data"),
            col(Flow.id).label("flow_id"),
            col(Flow.name).label("flow_name"),
            col(Flow.description).label("flow_description"),
            col(Flow.tags).label("flow_tags"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(
            FlowVersion,
            and_(
                FlowVersion.user_id == user_id,
                FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowVersion.flow_id,
                Flow.user_id == user_id,
                Flow.folder_id == project_id,
            ),
        )
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = "One or more flow version ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    artifacts: list[tuple[UUID, BaseFlowArtifact]] = []
    for row in rows:
        if row.flow_version_data is None:
            msg = f"Flow version {row.flow_version_id} has no data (snapshot may be corrupted)."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        artifacts.append(
            (
                row.flow_version_id,
                BaseFlowArtifact(
                    id=row.flow_id,
                    name=row.flow_name,
                    description=row.flow_description,
                    data=row.flow_version_data,
                    tags=row.flow_tags,
                ),
            )
        )
    return artifacts


async def validate_project_scoped_flow_version_ids(
    *,
    flow_version_ids: list[UUID],
    user_id: UUID,
    project_id: UUID,
    db,
) -> None:
    """Ensure all flow-version ids belong to flows in a specific project."""
    if not flow_version_ids:
        return
    unique_flow_version_ids = list(dict.fromkeys(flow_version_ids))
    matched_count = int(
        (
            await db.exec(
                select(func.count(FlowVersion.id))
                .select_from(FlowVersion)
                .join(
                    Flow,
                    and_(
                        Flow.id == FlowVersion.flow_id,
                        Flow.user_id == user_id,
                        Flow.folder_id == project_id,
                    ),
                )
                .where(
                    FlowVersion.user_id == user_id,
                    col(FlowVersion.id).in_(unique_flow_version_ids),
                )
            )
        ).one()
        or 0
    )
    if matched_count != len(unique_flow_version_ids):
        msg = "One or more flow version ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


# ---------------------------------------------------------------------------
# Route helpers (moved from langflow.api.v1.deployments)
# ---------------------------------------------------------------------------


def deployment_pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Params:
    return Params(page=page, size=size)


def page_offset(page: int, size: int) -> int:
    return (page - 1) * size


def raise_http_for_value_error(exc: ValueError) -> None:
    status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@contextmanager
def handle_adapter_errors(*, mapper: BaseDeploymentMapper | None = None):
    """Map deployment adapter exceptions to appropriate HTTP responses.

    Domain exceptions (subclasses of :class:`DeploymentServiceError`) are
    mapped via :func:`http_status_for_deployment_error` in the shared
    ``lfx.services.adapters.deployment.exceptions`` module.  Non-domain
    exceptions (``NotImplementedError``, ``ValueError``, etc.) are handled
    as special cases here.
    """
    try:
        yield
    except DeploymentServiceError as exc:
        http_status = http_status_for_deployment_error(exc)
        detail = exc.message
        if isinstance(exc, ResourceConflictError) and mapper is not None:
            detail = mapper.format_conflict_detail(
                exc.message,
                resource=exc.resource,
                resource_name=exc.resource_name,
            )
        logger.exception("Adapter error (status=%s): %s", http_status, detail)
        raise HTTPException(
            status_code=http_status,
            detail=detail,
        ) from exc
    except NotImplementedError as exc:
        logger.exception("Adapter not-implemented error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This operation is not supported by the deployment provider.",
        ) from exc
    except ValueError as exc:
        logger.exception("Adapter value error: %s", exc)
        raise_http_for_value_error(exc)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled adapter error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while communicating with the deployment provider.",
        ) from exc


async def flow_version_ids_for_flows(db, *, flow_ids: list[UUID], user_id: UUID) -> list[UUID]:
    """Return all flow-version IDs belonging to the given flows and user."""
    if not flow_ids:
        return []
    stmt = select(FlowVersion.id).where(
        col(FlowVersion.flow_id).in_(flow_ids),
        FlowVersion.user_id == user_id,
    )
    return list((await db.exec(stmt)).all())


async def get_owned_provider_account_or_404(
    *,
    provider_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> DeploymentProviderAccount:
    provider_account = await get_provider_account_row_by_id(db, provider_id=provider_id, user_id=user_id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    return provider_account


async def resolve_adapter_mapper_from_provider_id(
    provider_id: UUID,
    *,
    user_id: UUID,
    db: DbSession,
) -> tuple[DeploymentServiceProtocol, BaseDeploymentMapper]:
    from langflow.api.v1.mappers.deployments.registry import get_deployment_mapper

    provider_account = await get_owned_provider_account_or_404(provider_id=provider_id, user_id=user_id, db=db)
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    return deployment_adapter, get_deployment_mapper(provider_account.provider_key)


def resolve_deployment_adapter(
    provider_key: str,
) -> DeploymentServiceProtocol:
    try:
        adapter_key = require_non_empty(
            provider_key,
            "Deployment provider account has no provider_key configured.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        deployment_adapter = get_deployment_adapter(adapter_key)
    except Exception as exc:
        logger.exception("Failed to resolve deployment adapter for key '%s': %s", adapter_key, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    if deployment_adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No deployment adapter registered for provider_key '{adapter_key}'.",
        )
    return deployment_adapter


async def get_deployment_row_or_404(
    *,
    deployment_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> Deployment:
    deployment_row = await get_deployment_db(db, user_id=user_id, deployment_id=deployment_id)
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.")
    return deployment_row


async def resolve_adapter_from_deployment(
    *,
    deployment_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> tuple[Deployment, DeploymentServiceProtocol, str]:
    """Returns ``(deployment_row, adapter, provider_key)``."""
    deployment_row = await get_deployment_row_or_404(deployment_id=deployment_id, user_id=user_id, db=db)
    provider_account = await get_owned_provider_account_or_404(
        provider_id=deployment_row.deployment_provider_account_id,
        user_id=user_id,
        db=db,
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    return deployment_row, deployment_adapter, provider_account.provider_key


async def resolve_adapter_mapper_from_deployment(
    *,
    deployment_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> tuple[Deployment, DeploymentServiceProtocol, BaseDeploymentMapper, str]:
    """Returns ``(deployment_row, adapter, mapper, provider_key)``."""
    from langflow.api.v1.mappers.deployments.registry import get_deployment_mapper

    deployment_row = await get_deployment_row_or_404(deployment_id=deployment_id, user_id=user_id, db=db)
    provider_account = await get_owned_provider_account_or_404(
        provider_id=deployment_row.deployment_provider_account_id,
        user_id=user_id,
        db=db,
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    return deployment_row, deployment_adapter, deployment_mapper, provider_account.provider_key


async def resolve_project_id_for_deployment_create(
    *,
    payload: DeploymentCreateRequest,
    user_id: UUID,
    db: DbSession,
) -> UUID:
    if payload.project_id is not None:
        project = (
            await db.exec(
                select(Folder).where(
                    Folder.user_id == user_id,
                    Folder.id == payload.project_id,
                )
            )
        ).first()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return project.id

    default_folder = await get_or_create_default_folder(db, user_id)
    return default_folder.id


def resolve_snapshot_map_for_create(
    *,
    deployment_mapper: BaseDeploymentMapper,
    result: AdapterDeploymentCreateResult,
    flow_version_ids: list[UUID],
) -> dict[UUID, str]:
    if not flow_version_ids:
        return {}
    bindings = deployment_mapper.util_create_snapshot_bindings(
        result=result,
    )
    bindings_by_source_ref = bindings.to_source_ref_map()
    if not bindings_by_source_ref:
        msg = "Deployment provider create result is missing required snapshot bindings."
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
    expected_source_ref_to_flow_version_id = {
        str(flow_version_id): flow_version_id for flow_version_id in flow_version_ids
    }
    if len(bindings_by_source_ref) != len(expected_source_ref_to_flow_version_id):
        msg = (
            f"Snapshot binding count mismatch on create: {len(expected_source_ref_to_flow_version_id)} "
            f"flow versions vs {len(bindings_by_source_ref)} snapshot bindings"
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
    snapshot_id_by_flow_version_id: dict[UUID, str] = {}
    for source_ref, snapshot_id in bindings_by_source_ref.items():
        flow_version_id = expected_source_ref_to_flow_version_id.get(source_ref)
        if flow_version_id is None:
            msg = f"Unexpected source_ref in create snapshot bindings: {source_ref}"
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        snapshot_id_by_flow_version_id[flow_version_id] = snapshot_id
    return snapshot_id_by_flow_version_id


def resolve_flow_version_patch_for_update(
    *,
    deployment_mapper: BaseDeploymentMapper,
    payload: DeploymentUpdateRequest,
) -> tuple[list[UUID], list[UUID]]:
    patch = deployment_mapper.util_flow_version_patch(payload)
    return patch.add_flow_version_ids, patch.remove_flow_version_ids


async def rollback_provider_create(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    provider_id: UUID,
    resource_id: object,
    provider_result: Any | None = None,
    allow_delete_fallback: bool = True,
    user_id: UUID,
    db: DbSession,
) -> None:
    """Best-effort compensating cleanup after a failed DB commit on create."""
    # TODO: Add this method to the deployment service protocol.
    rollback_create_result = getattr(deployment_adapter, "rollback_create_result", None)
    if provider_result is not None and callable(rollback_create_result):
        try:
            with deployment_provider_scope(provider_id):
                await rollback_create_result(
                    deployment_id=str(resource_id),
                    provider_result=provider_result,
                    user_id=user_id,
                    db=db,
                )
        except Exception:  # noqa: BLE001
            if allow_delete_fallback:
                logger.warning(
                    "Extended rollback failed for provider resource %s on provider account %s; "
                    "falling back to basic delete.",
                    resource_id,
                    provider_id,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Extended rollback failed for existing provider resource %s on provider account %s; "
                    "skipping delete fallback.",
                    resource_id,
                    provider_id,
                    exc_info=True,
                )
                return
        else:
            logger.info(
                "Rolled back provider create result for resource %s on provider account %s after DB commit failure.",
                resource_id,
                provider_id,
            )
            return
    if not allow_delete_fallback:
        logger.warning(
            "Skipping delete fallback for existing provider resource %s on provider account %s; "
            "provider side-effects may require manual cleanup.",
            resource_id,
            provider_id,
        )
        return
    try:
        with deployment_provider_scope(provider_id):
            await deployment_adapter.delete(
                deployment_id=str(resource_id),
                user_id=user_id,
                db=db,
            )
        logger.info(
            "Rolled back provider resource %s on provider account %s after DB commit failure.",
            resource_id,
            provider_id,
        )
    except Exception:  # noqa: BLE001
        logger.critical(
            "Rollback failed: provider resource %s may be orphaned on provider account %s. "
            "Manual cleanup may be required.",
            resource_id,
            provider_id,
            exc_info=True,
        )


async def rollback_provider_update(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    deployment_mapper: BaseDeploymentMapper,
    deployment_db_id: UUID,
    deployment_resource_key: str,
    deployment_provider_account_id: UUID,
    user_id: UUID,
    db: DbSession,
) -> None:
    """Best-effort compensating update after a DB commit failure.

    The update handler uses a provider-first strategy — the provider
    has already been mutated by the time we attempt ``session.commit()``.  If
    that commit fails, the provider's state no longer matches the DB.  This
    function attempts to restore the provider to its pre-update state by
    reading the (unchanged) DB attachment rows and asking the mapper to build
    a compensating update payload.

    The caller must reset the session (``await db.rollback()``) before calling
    this function so that it is queryable.

    If the mapper returns ``None`` (rollback not supported for this provider),
    or any step fails, provider state may diverge until lazy read-path
    synchronization detects the inconsistency.
    """
    try:
        rollback_payload = await deployment_mapper.resolve_rollback_update(
            user_id=user_id,
            deployment_db_id=deployment_db_id,
            deployment_resource_key=deployment_resource_key,
            db=db,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to build rollback update payload for deployment %s (resource_key=%s). "
            "Provider state may diverge from DB.",
            deployment_db_id,
            deployment_resource_key,
            exc_info=True,
        )
        return

    if rollback_payload is None:
        logger.warning(
            "No rollback update payload available for deployment %s (resource_key=%s). "
            "Provider state may diverge from DB.",
            deployment_db_id,
            deployment_resource_key,
        )
        return

    try:
        with deployment_provider_scope(deployment_provider_account_id):
            await deployment_adapter.update(
                deployment_id=deployment_resource_key,
                payload=rollback_payload,
                user_id=user_id,
                db=db,
            )
        logger.info(
            "Rolled back provider update for deployment %s (resource_key=%s) after DB commit failure.",
            deployment_db_id,
            deployment_resource_key,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Compensating update failed for deployment %s (resource_key=%s). Provider state may diverge from DB.",
            deployment_db_id,
            deployment_resource_key,
            exc_info=True,
        )


async def list_deployments_synced(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    deployment_mapper: BaseDeploymentMapper,
    user_id: UUID,
    provider_id: UUID,
    db: DbSession,
    page: int,
    size: int,
    deployment_type: DeploymentType | None,
    flow_version_ids: list[UUID] | None = None,
    project_id: UUID | None = None,
) -> tuple[list[tuple[Deployment, int, list[tuple[UUID, str | None]]]], int]:
    """Return a page of deployments, deleting any DB rows the provider doesn't recognise.

    Fetches DB rows in batches, sends each batch's resource keys to the
    provider for validation, and deletes stale rows inline. The cursor does
    not advance for deleted rows (deletion shifts subsequent offsets down).
    """
    accepted: list[tuple[Deployment, int, list[tuple[UUID, str | None]]]] = []
    accepted_deployment_ids: list[UUID] = []
    provider_bindings: list[ProviderSnapshotBinding] = []
    cursor = page_offset(page, size)
    max_sync_rounds = 2  # Initial pass + one refill pass.
    for _ in range(max_sync_rounds):
        if len(accepted) >= size:
            break
        batch = await list_deployments_page(
            db,
            user_id=user_id,
            deployment_provider_account_id=provider_id,
            offset=cursor,
            limit=size - len(accepted),
            flow_version_ids=flow_version_ids,
            project_id=project_id,
        )
        if not batch:
            break

        known, provider_view = await fetch_provider_resource_keys(
            deployment_adapter=deployment_adapter,
            user_id=user_id,
            provider_id=provider_id,
            db=db,
            resource_keys=[row.resource_key for row, _, _ in batch],
            deployment_type=deployment_type,
        )
        provider_bindings.extend(deployment_mapper.extract_snapshot_bindings(provider_view))

        for row, attached_count, matched_flow_versions in batch:
            if row.resource_key not in known:
                # Provider `known` is type-filtered; skip other local types instead of deleting as stale.
                if deployment_type is not None and row.deployment_type != deployment_type:
                    cursor += 1
                    continue
                logger.warning(
                    "Deployment %s (resource_key=%s) not found on provider %s — deleting stale row",
                    row.id,
                    row.resource_key,
                    provider_id,
                )
                await delete_deployment_by_id(db, user_id=user_id, deployment_id=row.id)
                continue
            accepted.append((row, attached_count, matched_flow_versions))
            accepted_deployment_ids.append(row.id)
            cursor += 1

    # Phase 2: binding-level sync.
    # Remove stale local attachments based on provider bindings, then recount.
    # Best-effort - provider or DB failures should not block the list response.
    if accepted:
        try:
            async with db.begin_nested():
                await delete_unbound_attachments(
                    db,
                    user_id=user_id,
                    provider_account_id=provider_id,
                    deployment_ids=accepted_deployment_ids,
                    bindings=provider_bindings,
                )

            corrected_counts = await count_attachments_by_deployment_ids(
                db,
                user_id=user_id,
                deployment_ids=accepted_deployment_ids,
            )
            accepted = [(row, corrected_counts[row.id], matched) for row, _attached_count, matched in accepted]
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for list_deployments_synced; returning unverified attachment counts",
                exc_info=True,
            )

    total = await count_deployments_by_provider(
        db,
        user_id=user_id,
        deployment_provider_account_id=provider_id,
        flow_version_ids=flow_version_ids,
        project_id=project_id,
    )
    return accepted, total


async def list_deployment_flow_versions_synced(
    *,
    deployment_adapter: DeploymentServiceProtocol,
    user_id: UUID,
    provider_id: UUID,
    deployment_id: UUID,
    db: DbSession,
    page: int,
    size: int,
    flow_ids: list[UUID] | None = None,
) -> tuple[list[tuple[FlowVersionDeploymentAttachment, FlowVersion, str | None]], int, SnapshotListResult | None]:
    """Return a paginated deployment attachment view synced against provider snapshots.

    Uses attachment-tracked ``provider_snapshot_id`` values to verify provider
    snapshot existence in one batched adapter call. Stale attachments are
    deleted before pagination is applied.
    """
    attachments = await list_deployment_attachments(
        db,
        user_id=user_id,
        deployment_id=deployment_id,
        flow_ids=flow_ids,
    )
    snapshot_result: SnapshotListResult | None = None
    verified_snapshot_ids = extract_verified_snapshot_ids(attachments)
    snapshot_ids = list(dict.fromkeys(verified_snapshot_ids))
    if snapshot_ids:
        try:
            snapshot_result = await deployment_adapter.list_snapshots(
                user_id=user_id,
                db=db,
                params=SnapshotListParams(snapshot_ids=snapshot_ids),
            )
            known_snapshot_ids = extract_verified_provider_snapshot_ids(snapshot_result)

            async with db.begin_nested():
                await sync_attachment_snapshot_ids(
                    user_id=user_id,
                    attachments=attachments,
                    known_snapshot_ids=known_snapshot_ids,
                    db=db,
                )
        except Exception as exc:  # noqa: BLE001
            snapshot_result = None
            logger.warning(
                "Snapshot-level sync failed while listing deployment flow versions for deployment %s "
                "(provider %s): %s; "
                "returning DB rows without provider enrichment",
                deployment_id,
                provider_id,
                exc,
                exc_info=True,
            )

    rows = await list_deployment_attachments_with_versions(
        db,
        user_id=user_id,
        deployment_id=deployment_id,
        offset=page_offset(page, size),
        limit=size,
        flow_ids=flow_ids,
    )
    total = await count_deployment_attachments(
        db,
        user_id=user_id,
        deployment_id=deployment_id,
        flow_ids=flow_ids,
    )
    return rows, total, snapshot_result


async def attach_flow_versions(
    *,
    flow_version_ids: list[UUID],
    user_id: UUID,
    deployment_row_id: UUID,
    snapshot_id_by_flow_version_id: dict[UUID, str] | None = None,
    db: DbSession,
) -> None:
    if not flow_version_ids:
        return

    for flow_version_id in flow_version_ids:
        snapshot_id = require_non_empty(
            (snapshot_id_by_flow_version_id or {}).get(flow_version_id),
            "Missing provider snapshot binding for flow version "
            f"{flow_version_id} during deployment attachment creation.",
        )
        await create_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_id,
            deployment_id=deployment_row_id,
            provider_snapshot_id=snapshot_id,
        )


async def apply_flow_version_patch_attachments(
    *,
    user_id: UUID,
    deployment_row_id: UUID,
    added_snapshot_bindings: list[tuple[UUID, str]],
    remove_flow_version_ids: list[UUID],
    db: DbSession,
) -> None:
    for flow_version_uuid, snapshot_id in added_snapshot_bindings:
        existing = await get_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_uuid,
            deployment_id=deployment_row_id,
        )
        if existing is None:
            await create_deployment_attachment(
                db,
                user_id=user_id,
                flow_version_id=flow_version_uuid,
                deployment_id=deployment_row_id,
                provider_snapshot_id=snapshot_id,
            )
            continue
        if existing.provider_snapshot_id != snapshot_id:
            await update_deployment_attachment_provider_snapshot_id(
                db,
                attachment=existing,
                provider_snapshot_id=snapshot_id,
            )

    for flow_version_uuid in remove_flow_version_ids:
        await delete_deployment_attachment(
            db,
            user_id=user_id,
            flow_version_id=flow_version_uuid,
            deployment_id=deployment_row_id,
        )


def resolve_added_snapshot_bindings_for_update(
    *,
    deployment_mapper: BaseDeploymentMapper,
    added_flow_version_ids: list[UUID],
    result: DeploymentUpdateResult,
) -> list[tuple[UUID, str]]:
    if not added_flow_version_ids:
        return []
    bindings = deployment_mapper.util_update_snapshot_bindings(
        result=result,
    )
    bindings_by_source_ref = bindings.to_source_ref_map()
    expected_source_ref_to_flow_version_id: dict[str, UUID] = {
        str(flow_version_id): flow_version_id for flow_version_id in added_flow_version_ids
    }

    unexpected_source_refs = sorted(
        source_ref for source_ref in bindings_by_source_ref if source_ref not in expected_source_ref_to_flow_version_id
    )
    if unexpected_source_refs:
        msg = f"Unexpected source_ref in update snapshot bindings: {unexpected_source_refs}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)

    snapshot_bindings: list[tuple[UUID, str]] = []
    missing_source_refs: list[str] = []
    for source_ref, flow_version_id in expected_source_ref_to_flow_version_id.items():
        snapshot_id = bindings_by_source_ref.get(source_ref)
        if snapshot_id is None:
            missing_source_refs.append(source_ref)
            continue
        snapshot_bindings.append((flow_version_id, snapshot_id))
    if missing_source_refs:
        msg = f"Missing snapshot bindings for added flow versions on update: {missing_source_refs}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
    return snapshot_bindings
