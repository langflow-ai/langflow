import copy
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from lfx.log import logger
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.core import strip_secret_field_values
from langflow.api.v1.flows import _validate_catalog_policy_for_write
from langflow.api.v1.mappers.deployments.helpers import get_owned_provider_account_or_404
from langflow.api.v1.mappers.deployments.sync import sync_flow_version_attachments
from langflow.api.v1.schemas.flow_version_diff import DiffSideRef, FlowVersionDiffResponse
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_version.crud import (
    create_flow_version_entry,
    delete_flow_version_entry,
    get_flow_version_entry_or_raise,
    get_flow_version_list_simple,
    get_flow_versions_with_provider_status,
)
from langflow.services.database.models.flow_version.exceptions import (
    FlowVersionConflictError,
    FlowVersionDeployedError,
    FlowVersionError,
    FlowVersionNotFoundError,
    FlowVersionSerializationError,
)
from langflow.services.database.models.flow_version.model import (
    FlowVersion,
    FlowVersionCreate,
    FlowVersionListResponse,
    FlowVersionRead,
    FlowVersionReadWithData,
)
from langflow.services.deps import get_catalog_policy_service, get_settings_service
from langflow.utils.flow_diff import FlowDiffSide, FlowDiffStripError, compute_flow_diff

router = APIRouter(prefix="/flows/{flow_id}/versions", tags=["Flow Versions"], include_in_schema=False)

# Sentinel for the ``against`` query parameter, meaning the live flow draft rather
# than a stored version.
DRAFT_COMPARISON_TARGET = "draft"


def strip_version_data(data: dict | None) -> dict | None:
    """Strip secret field values from a version entry's flow data dict.

    Uses the metadata-driven scrubber, so ``password``-marked fields under
    ordinary names and credential-bearing connection strings are cleared too --
    not only fields whose name matches the legacy API-key pattern.

    Returns None if stripping fails, to prevent accidental secret leakage.
    """
    if data is None:
        return None
    try:
        return strip_secret_field_values(data)
    except (KeyError, TypeError, AttributeError, ValueError):
        logger.warning(
            "Failed to strip API keys from version data — excluding data from response to prevent secret leakage",
            exc_info=True,
        )
        return None


def _version_to_read(entry: FlowVersion, *, is_deployed: bool | None = None) -> FlowVersionRead:
    result = FlowVersionRead.model_validate(entry, from_attributes=True)
    result.is_deployed = is_deployed
    return result


def _version_to_read_full(
    entry: FlowVersion, *, strip_keys: bool = False, is_deployed: bool | None = None
) -> FlowVersionReadWithData:
    result = FlowVersionReadWithData.model_validate(entry, from_attributes=True)
    result.is_deployed = is_deployed
    if strip_keys:
        result.data = strip_version_data(result.data)
    return result


async def _get_user_flow(session: AsyncSession, flow_id: UUID, user_id: UUID) -> Flow:
    result = await session.exec(select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id))
    flow = result.first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


def _translate_version_error(exc: FlowVersionError) -> HTTPException:
    """Translate a domain exception into an HTTPException."""
    if isinstance(exc, FlowVersionSerializationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, FlowVersionConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, FlowVersionDeployedError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, FlowVersionNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _ensure_deployments_enabled_for_provider_id(deployment_provider_id: UUID | None) -> None:
    if deployment_provider_id and not FEATURE_FLAGS.wxo_deployments:
        msg = "Cannot use deployment_provider_id: the wxo_deployments feature flag is disabled"
        raise HTTPException(status_code=400, detail=msg)


# NOTE: `response_model_exclude_none=True` is intentionally narrow here: we use
# it to omit `is_deployed` unless deployment status is explicitly requested.
# If future nullable fields must be returned as explicit null, prefer splitting
# response schemas/routes and disabling this global exclude-none behavior.
@router.get("/", response_model_exclude_none=True)
async def list_flow_versions(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    deployment_provider_id: Annotated[
        UUID | None,
        Query(description=("Optional provider account ID for provider account-scoped deployment status.")),
    ] = None,
) -> FlowVersionListResponse:
    await _get_user_flow(session, flow_id, current_user.id)
    _ensure_deployments_enabled_for_provider_id(deployment_provider_id)

    if deployment_provider_id is not None:
        await get_owned_provider_account_or_404(
            provider_id=deployment_provider_id,
            user_id=current_user.id,
            db=session,
        )
        # Best-effort provider-scoped sync before read to keep status fresh.
        try:
            await sync_flow_version_attachments(
                db=session,
                flow_id=flow_id,
                user_id=current_user.id,
                deployment_provider_account_id=deployment_provider_id,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for flow %s; returning unverified deployment status",
                flow_id,
                exc_info=True,
            )

    if deployment_provider_id is not None:
        rows = await get_flow_versions_with_provider_status(
            session,
            flow_id,
            current_user.id,
            provider_account_id=deployment_provider_id,
            limit=limit,
            offset=offset,
        )
        entries = [_version_to_read(entry, is_deployed=is_deployed) for entry, is_deployed in rows]
    else:
        rows_simple = await get_flow_version_list_simple(
            session,
            flow_id,
            current_user.id,
            limit,
            offset,
        )
        entries = [_version_to_read(entry, is_deployed=None) for entry, _is_deployed in rows_simple]

    max_entries = get_settings_service().settings.max_flow_version_entries_per_flow
    return FlowVersionListResponse(
        entries=entries,
        max_entries=max_entries,
    )


# TODO: Full-version export endpoint (export flow with all version entries embedded).
# This is planned as a follow-up feature. The per-version export (exporting a single
# version as a standalone flow) is available via the GET /{version_id} endpoint.


@router.get("/{version_id}")
async def get_single_flow_version(
    flow_id: UUID,
    version_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> FlowVersionReadWithData:
    await _get_user_flow(session, flow_id, current_user.id)

    try:
        entry = await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Version entry not found") from exc

    return _version_to_read_full(entry, strip_keys=True)


def _draft_side_ref(flow: Flow) -> DiffSideRef:
    """Describe the live draft as one side of a comparison."""
    return DiffSideRef(kind="draft", created_at=flow.updated_at)


def _version_side_ref(entry: FlowVersion) -> DiffSideRef:
    """Describe a stored version as one side of a comparison."""
    return DiffSideRef(
        kind="version",
        version_id=entry.id,
        version_number=entry.version_number,
        version_tag=f"v{entry.version_number}",
        description=entry.description,
        created_at=entry.created_at,
    )


def _diff_side(data: dict | None) -> FlowDiffSide:
    """Pair a raw payload with its scrubbed counterpart for the diff engine.

    This is the only place either side of a diff is scrubbed, and it is
    unconditional. ``compute_flow_diff`` refuses to run if scrubbing failed
    closed, so a scrubber failure can never degrade into publishing raw data.
    """
    return FlowDiffSide(raw=data, stripped=strip_version_data(data))


# Two path segments, so this cannot be shadowed by the GET /{version_id} route
# above. A flat GET /diff?base=..&target=.. would be, and would 422 on UUID parsing.
@router.get("/{version_id}/diff", response_model_exclude_unset=True)
async def get_flow_version_diff(
    flow_id: UUID,
    version_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    against: Annotated[
        str,
        Query(description="A version id to compare against, or 'draft' for the live flow."),
    ] = DRAFT_COMPARISON_TARGET,
) -> FlowVersionDiffResponse:
    flow = await _get_user_flow(session, flow_id, current_user.id)
    await ensure_flow_permission(
        current_user,
        FlowAction.READ,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    try:
        base_entry = await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Version entry not found") from exc

    if against == DRAFT_COMPARISON_TARGET:
        target_ref = _draft_side_ref(flow)
        target_data = flow.data
    else:
        try:
            target_version_id = UUID(against)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid 'against' value — expected a version id or 'draft'.",
            ) from exc
        try:
            # Passing flow_id here is what makes a version from another flow a 404
            # rather than a cross-flow comparison.
            target_entry = await get_flow_version_entry_or_raise(
                session, target_version_id, current_user.id, flow_id=flow_id
            )
        except FlowVersionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Version entry not found") from exc
        target_ref = _version_side_ref(target_entry)
        target_data = target_entry.data

    try:
        diff = compute_flow_diff(_diff_side(base_entry.data), _diff_side(target_data))
    except FlowDiffStripError as exc:
        raise HTTPException(
            status_code=422,
            detail="Version data could not be prepared for comparison.",
        ) from exc

    return FlowVersionDiffResponse.model_validate({"base": _version_side_ref(base_entry), "target": target_ref, **diff})


# shares FlowVersionRead model with list endpoint (inside FlowVersionListResponse),
# but omits is_deployed field because its not relevant to this endpoint
@router.post("/", status_code=201, response_model_exclude={"is_deployed"})
async def create_snapshot(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    body: FlowVersionCreate | None = None,
) -> FlowVersionRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)
    await ensure_flow_permission(
        current_user,
        FlowAction.WRITE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )
    description = body.description if body else None

    try:
        data = copy.deepcopy(flow.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied for snapshot. The data may be corrupted.",
        ) from exc

    try:
        entry = await create_flow_version_entry(
            session,
            flow_id=flow.id,
            user_id=current_user.id,
            data=data,
            description=description,
        )
    except FlowVersionError as exc:
        raise _translate_version_error(exc) from exc
    return _version_to_read(entry)


@router.post("/{version_id}/activate")
async def activate_version(
    flow_id: UUID,
    version_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    *,
    save_draft: Annotated[bool, Query()] = True,
) -> FlowRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)
    await ensure_flow_permission(
        current_user,
        FlowAction.WRITE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    # Verify version entry belongs to this flow
    try:
        target_entry = await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Version entry not found") from exc

    # Guard against activating a version with no data (check before auto-snapshot)
    if target_entry.data is None:
        raise HTTPException(status_code=400, detail="Cannot activate a version with no data")

    # Capture copies of both data dicts before the savepoint to avoid stale
    # reads if pruning inside create_flow_version_entry deletes old entries.
    try:
        current_data = copy.deepcopy(flow.data) if save_draft else None
        target_data = copy.deepcopy(target_entry.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied. The data may be corrupted.",
        ) from exc

    _validate_catalog_policy_for_write(
        target_data,
        snapshot=get_catalog_policy_service().snapshot,
    )

    # Wrap auto-snapshot + flow overwrite in a single savepoint for atomicity.
    # If the flow update fails, the auto-snapshot is also rolled back.
    try:
        async with session.begin_nested():
            if save_draft and current_data is not None:
                await create_flow_version_entry(
                    session,
                    flow_id=flow.id,
                    user_id=current_user.id,
                    data=current_data,
                    description=f"Auto-saved before activating v{target_entry.version_number}",
                )

            flow.data = target_data
            flow.updated_at = datetime.now(timezone.utc)

            session.add(flow)
            await session.flush()
    except FlowVersionError as exc:
        raise _translate_version_error(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Could not activate version — the flow was modified concurrently. Please try again.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Database error while activating version. Please try again.",
        ) from exc

    await logger.adebug("Activated version %s (%s) for flow %s", version_id, f"v{target_entry.version_number}", flow_id)

    return FlowRead.model_validate(flow, from_attributes=True)


@router.delete("/{version_id}", status_code=204)
async def delete_version_entry(
    flow_id: UUID,
    version_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    flow = await _get_user_flow(session, flow_id, current_user.id)
    await ensure_flow_permission(
        current_user,
        FlowAction.DELETE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    # Verify entry belongs to this flow, then delete
    try:
        await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
        await delete_flow_version_entry(session, version_id, current_user.id)
    except FlowVersionError as exc:
        raise _translate_version_error(exc) from exc
    await logger.adebug("Deleted version entry %s for flow %s", version_id, flow_id)
