from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_history.crud import (
    archive_previously_published,
    create_flow_history_entry,
    delete_flow_history_entry,
    get_flow_history_entry,
    get_flow_history_list,
    set_entry_state,
)
from langflow.services.database.models.flow_history.model import (
    FlowHistory,
    FlowHistoryCreate,
    FlowHistoryRead,
    FlowHistoryReadFull,
    FlowStateEnum,
)

router = APIRouter(prefix="/flows/{flow_id}/history", tags=["Flow History"])


def _history_to_read(entry: FlowHistory) -> FlowHistoryRead:
    return FlowHistoryRead(
        id=entry.id,
        flow_id=entry.flow_id,
        user_id=entry.user_id,
        state=entry.state,
        version_number=entry.version_number,
        version_tag=entry.version_tag,
        description=entry.description,
        created_at=entry.created_at,
    )


def _history_to_read_full(entry: FlowHistory) -> FlowHistoryReadFull:
    return FlowHistoryReadFull(
        id=entry.id,
        flow_id=entry.flow_id,
        user_id=entry.user_id,
        state=entry.state,
        version_number=entry.version_number,
        version_tag=entry.version_tag,
        description=entry.description,
        created_at=entry.created_at,
        data=entry.data,
    )


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
        entries = await get_flow_history_list(session, flow_id, current_user.id, limit=10000, offset=0)
        flow_dict["history"] = [
            {
                "version_number": e.version_number,
                "description": e.description,
                "state": e.state.value if hasattr(e.state, "value") else str(e.state),
                "data": e.data,
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
    entry = await create_flow_history_entry(
        session,
        flow_id=flow.id,
        user_id=current_user.id,
        data=copy.deepcopy(flow.data),
        description=description,
        state=FlowStateEnum.DRAFT,
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

    # Auto-snapshot: save current draft before overwriting
    await create_flow_history_entry(
        session,
        flow_id=flow.id,
        user_id=current_user.id,
        data=copy.deepcopy(flow.data),
        description=f"Auto-saved before activating {target_entry.version_tag}",
        state=FlowStateEnum.DRAFT,
    )

    # Guard against activating a version with no data
    if target_entry.data is None:
        raise HTTPException(status_code=400, detail="Cannot activate a version with no data")

    # Overwrite flow data with the activated version's data
    flow.data = copy.deepcopy(target_entry.data)
    flow.active_version_id = history_id
    flow.updated_at = datetime.now(timezone.utc)

    # Update states using targeted SQL UPDATEs (avoids loading all entries into memory)
    await archive_previously_published(session, flow_id, exclude_id=history_id)
    await set_entry_state(session, history_id, FlowStateEnum.PUBLISHED)

    flow.state = FlowStateEnum.PUBLISHED
    session.add(flow)
    await session.flush()

    return FlowRead.model_validate(flow, from_attributes=True)


@router.delete("/{history_id}", status_code=204)
async def delete_history_entry(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    flow = await _get_user_flow(session, flow_id, current_user.id)

    # Verify entry belongs to this flow
    entry = await get_flow_history_entry(session, history_id, current_user.id)
    if not entry or entry.flow_id != flow_id:
        raise HTTPException(status_code=404, detail="History entry not found")

    await delete_flow_history_entry(session, history_id, current_user.id, flow.active_version_id)
