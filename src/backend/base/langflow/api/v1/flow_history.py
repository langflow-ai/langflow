from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from lfx.log import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.utils.core import remove_api_keys
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_history.crud import (
    create_flow_history_entry,
    delete_flow_history_entry,
    get_flow_history_entry,
    get_flow_history_list,
)
from langflow.services.database.models.flow_history.model import (
    FlowHistory,
    FlowHistoryCreate,
    FlowHistoryRead,
    FlowHistoryReadFull,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/flows/{flow_id}/history", tags=["Flow History"])


def _strip_history_data(data: dict | None) -> dict | None:
    """Strip API keys from a history entry's flow data dict."""
    if data is None:
        return None
    data_copy = copy.deepcopy(data)
    try:
        return remove_api_keys({"data": data_copy}).get("data")
    except (AttributeError, KeyError, TypeError):
        return data_copy


def _history_to_read(entry: FlowHistory) -> FlowHistoryRead:
    return FlowHistoryRead.model_validate(entry, from_attributes=True)


def _history_to_read_full(entry: FlowHistory) -> FlowHistoryReadFull:
    return FlowHistoryReadFull.model_validate(entry, from_attributes=True)


async def _get_user_flow(session: AsyncSession, flow_id: UUID, user_id: UUID) -> Flow:
    result = await session.exec(select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id))
    flow = result.first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.get("/")
async def list_flow_history(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[FlowHistoryRead]:
    await _get_user_flow(session, flow_id, current_user.id)
    entries = await get_flow_history_list(session, flow_id, current_user.id, limit, offset)
    return [_history_to_read(e) for e in entries]


@router.get("/export")
async def export_flow_with_history(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
    include_history: bool = True,
) -> dict:
    """Return the flow as a dict with optional version history embedded."""
    flow = await _get_user_flow(session, flow_id, current_user.id)
    flow_dict = FlowRead.model_validate(flow, from_attributes=True).model_dump()

    if include_history:
        max_entries = get_settings_service().settings.max_flow_history_entries_per_flow
        entries = await get_flow_history_list(session, flow_id, current_user.id, limit=max_entries, offset=0)
        flow_dict["history"] = [
            {
                "version_number": e.version_number,
                "description": e.description,
                "data": _strip_history_data(e.data),
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]

    return flow_dict


@router.get("/{history_id}")
async def get_single_flow_history(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> FlowHistoryReadFull:
    await _get_user_flow(session, flow_id, current_user.id)
    entry = await get_flow_history_entry(session, history_id, current_user.id)
    if not entry or entry.flow_id != flow_id:
        raise HTTPException(status_code=404, detail="History entry not found")
    return _history_to_read_full(entry)


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
    entry = await create_flow_history_entry(
        session,
        flow_id=flow.id,
        user_id=current_user.id,
        data=data,
        description=description,
    )
    return _history_to_read(entry)


@router.post("/{history_id}/activate")
async def activate_version(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> FlowRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)

    # Verify history entry belongs to this flow
    target_entry = await get_flow_history_entry(session, history_id, current_user.id)
    if not target_entry or target_entry.flow_id != flow_id:
        raise HTTPException(status_code=404, detail="History entry not found")

    # Guard against activating a version with no data (check before auto-snapshot)
    if target_entry.data is None:
        raise HTTPException(status_code=400, detail="Cannot activate a version with no data")

    # Capture copies of both data dicts before the savepoint to avoid stale
    # reads if pruning inside create_flow_history_entry deletes old entries.
    try:
        current_data = copy.deepcopy(flow.data)
        target_data = copy.deepcopy(target_entry.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied. The data may be corrupted.",
        ) from exc

    # Wrap auto-snapshot + flow overwrite in a single savepoint for atomicity.
    # If the flow update fails, the auto-snapshot is also rolled back.
    async with session.begin_nested():
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

    # Verify entry belongs to this flow
    entry = await get_flow_history_entry(session, history_id, current_user.id)
    if not entry or entry.flow_id != flow_id:
        raise HTTPException(status_code=404, detail="History entry not found")

    await delete_flow_history_entry(session, history_id, current_user.id)
    await logger.adebug("Deleted history entry %s for flow %s", history_id, flow_id)
