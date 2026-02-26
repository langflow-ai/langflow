from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from lfx.log import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.utils.core import remove_api_keys
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_history.crud import (
    create_flow_history_entry,
    delete_flow_history_entry,
    get_flow_history_entry_or_raise,
    get_flow_history_list,
)
from langflow.services.database.models.flow_history.exceptions import (
    FlowHistoryDataTooLargeError,
    FlowHistoryError,
    FlowHistoryNotFoundError,
    FlowHistorySerializationError,
    FlowHistoryVersionConflictError,
)
from langflow.services.database.models.flow_history.model import (
    FlowHistory,
    FlowHistoryCreate,
    FlowHistoryListResponse,
    FlowHistoryRead,
    FlowHistoryReadWithData,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/flows/{flow_id}/history", tags=["Flow History"])


def strip_history_data(data: dict | None) -> dict | None:
    """Strip API keys from a history entry's flow data dict.

    Returns None on unexpected failure to prevent secret leakage.
    """
    if data is None:
        return None
    data_copy = copy.deepcopy(data)
    try:
        return remove_api_keys({"data": data_copy}).get("data")
    except Exception:
        logger.warning(
            "Failed to strip API keys from history data — excluding data from export to prevent secret leakage",
            exc_info=True,
        )
        return None


def _history_to_read(entry: FlowHistory) -> FlowHistoryRead:
    return FlowHistoryRead.model_validate(entry, from_attributes=True)


def _history_to_read_full(entry: FlowHistory, *, strip_keys: bool = False) -> FlowHistoryReadWithData:
    result = FlowHistoryReadWithData.model_validate(entry, from_attributes=True)
    if strip_keys:
        result.data = strip_history_data(result.data)
    return result


async def _get_user_flow(session: AsyncSession, flow_id: UUID, user_id: UUID) -> Flow:
    result = await session.exec(select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id))
    flow = result.first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


def _translate_history_error(exc: FlowHistoryError) -> HTTPException:
    """Translate a domain exception into an HTTPException."""
    if isinstance(exc, FlowHistorySerializationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, FlowHistoryDataTooLargeError):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, FlowHistoryVersionConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, FlowHistoryNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/")
async def list_flow_history(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> FlowHistoryListResponse:
    await _get_user_flow(session, flow_id, current_user.id)
    entries = await get_flow_history_list(session, flow_id, current_user.id, limit, offset)
    max_entries = get_settings_service().settings.max_flow_history_entries_per_flow
    return FlowHistoryListResponse(
        entries=[_history_to_read(e) for e in entries],
        max_entries=max_entries,
    )


# TODO: Full-history export endpoint (export flow with all history entries embedded).
# This is planned as a follow-up feature. The per-version export (exporting a single
# version as a standalone flow) is available via the GET /{history_id} endpoint.


@router.get("/{history_id}")
async def get_single_flow_history(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> FlowHistoryReadWithData:
    await _get_user_flow(session, flow_id, current_user.id)
    try:
        entry = await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
    except FlowHistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="History entry not found") from exc
    return _history_to_read_full(entry, strip_keys=True)


@router.post("/", status_code=201)
async def create_snapshot(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    body: FlowHistoryCreate | None = None,
) -> FlowHistoryRead:
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
        entry = await create_flow_history_entry(
            session,
            flow_id=flow.id,
            user_id=current_user.id,
            data=data,
            description=description,
        )
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
    return _history_to_read(entry)


@router.post("/{history_id}/activate")
async def activate_version(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    save_draft: bool = Query(default=True),
) -> FlowRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)

    # Verify history entry belongs to this flow
    try:
        target_entry = await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
    except FlowHistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="History entry not found") from exc

    # Guard against activating a version with no data (check before auto-snapshot)
    if target_entry.data is None:
        raise HTTPException(status_code=400, detail="Cannot activate a version with no data")

    # Capture copies of both data dicts before the savepoint to avoid stale
    # reads if pruning inside create_flow_history_entry deletes old entries.
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
                await create_flow_history_entry(
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
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
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

    await logger.adebug("Activated version %s (%s) for flow %s", history_id, f"v{target_entry.version_number}", flow_id)

    return FlowRead.model_validate(flow, from_attributes=True)


@router.delete("/{history_id}", status_code=204)
async def delete_history_entry(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    await _get_user_flow(session, flow_id, current_user.id)

    # Verify entry belongs to this flow, then delete
    try:
        await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
        await delete_flow_history_entry(session, history_id, current_user.id)
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
    await logger.adebug("Deleted history entry %s for flow %s", history_id, flow_id)
