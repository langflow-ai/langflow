import copy
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from lfx.log import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.core import remove_api_keys
from langflow.api.v1.mappers.deployments.helpers import sync_flow_version_attachments
from langflow.services.database.models.deployment_provider_account.crud import (
    count_provider_accounts,
)
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_version.crud import (
    create_flow_version_entry,
    delete_flow_version_entry,
    get_flow_version_entry_or_raise,
    get_flow_version_list,
    get_flow_version_list_simple,
    is_flow_version_deployed,
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
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/flows/{flow_id}/versions", tags=["Flow Versions"], include_in_schema=False)


def strip_version_data(data: dict | None) -> dict | None:
    """Strip API keys from a version entry's flow data dict.

    Returns None if stripping fails, to prevent accidental secret leakage.
    """
    if data is None:
        return None
    data_copy = copy.deepcopy(data)
    try:
        return remove_api_keys({"data": data_copy}).get("data")
    except (KeyError, TypeError, AttributeError, ValueError):
        logger.warning(
            "Failed to strip API keys from version data — excluding data from response to prevent secret leakage",
            exc_info=True,
        )
        return None


def _version_to_read(entry: FlowVersion, *, is_deployed: bool = False) -> FlowVersionRead:
    result = FlowVersionRead.model_validate(entry, from_attributes=True)
    result.is_deployed = is_deployed
    return result


def _version_to_read_full(
    entry: FlowVersion, *, strip_keys: bool = False, is_deployed: bool = False
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


@router.get("/")
async def list_flow_versions(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    deployment_ids: Annotated[
        list[UUID] | None,
        Query(
            description=(
                "Optional deployment ids to filter by (pass as repeated query params, "
                "e.g. ?deployment_ids=id1&deployment_ids=id2). When provided, only "
                "versions attached to at least one of these deployments are returned."
            ),
        ),
    ] = None,
) -> FlowVersionListResponse:
    await _get_user_flow(session, flow_id, current_user.id)

    has_providers = await count_provider_accounts(session, user_id=current_user.id) > 0

    if has_providers:
        # Best-effort snapshot-level sync: prune attachment rows whose
        # provider_snapshot_id is no longer recognised by the provider.
        try:
            await sync_flow_version_attachments(db=session, flow_id=flow_id, user_id=current_user.id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for flow %s; returning unverified deployment status",
                flow_id,
                exc_info=True,
            )

        rows = await get_flow_version_list(
            session,
            flow_id,
            current_user.id,
            limit,
            offset,
            deployment_ids=deployment_ids,
        )
    else:
        rows = await get_flow_version_list_simple(
            session,
            flow_id,
            current_user.id,
            limit,
            offset,
        )

    max_entries = get_settings_service().settings.max_flow_version_entries_per_flow
    return FlowVersionListResponse(
        entries=[_version_to_read(entry, is_deployed=is_deployed) for entry, is_deployed in rows],
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

    has_providers = await count_provider_accounts(session, user_id=current_user.id) > 0

    if has_providers:
        # Best-effort snapshot-level sync (same as list endpoint).
        try:
            await sync_flow_version_attachments(db=session, flow_id=flow_id, user_id=current_user.id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for flow %s; returning unverified deployment status",
                flow_id,
                exc_info=True,
            )

    try:
        entry = await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
    except FlowVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Version entry not found") from exc

    deployed = await is_flow_version_deployed(session, version_id) if has_providers else False
    return _version_to_read_full(entry, strip_keys=True, is_deployed=deployed)


@router.post("/", status_code=201)
async def create_snapshot(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    body: FlowVersionCreate | None = None,
) -> FlowVersionRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)
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
    await _get_user_flow(session, flow_id, current_user.id)

    # Verify entry belongs to this flow, then delete
    try:
        await get_flow_version_entry_or_raise(session, version_id, current_user.id, flow_id=flow_id)
        await delete_flow_version_entry(session, version_id, current_user.id)
    except FlowVersionError as exc:
        raise _translate_version_error(exc) from exc
    await logger.adebug("Deleted version entry %s for flow %s", version_id, flow_id)
