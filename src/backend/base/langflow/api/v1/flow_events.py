from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_flow_events_service
from langflow.services.flow_events import FlowEventsService

router = APIRouter(prefix="/flows", tags=["Flow Events"])


class FlowEventResponse(BaseModel):
    type: str
    timestamp: float
    summary: str


class FlowEventsResponse(BaseModel):
    events: list[FlowEventResponse]
    settled: bool


class FlowEventCreate(BaseModel):
    type: str
    summary: str = ""


async def _verify_flow_owner(session: DbSession, flow_id: UUID, user_id: UUID) -> None:
    result = await session.exec(select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id))
    if not result.first():
        raise HTTPException(status_code=404, detail="Flow not found")


@router.get("/{flow_id}/events", response_model=FlowEventsResponse)
async def get_flow_events(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    since: Annotated[float, Query(description="UTC timestamp to get events after")] = 0.0,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventsResponse:
    await _verify_flow_owner(session, flow_id, current_user.id)
    events, settled = service.get_since(str(flow_id), since)
    return FlowEventsResponse(
        events=[FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary) for e in events],
        settled=settled,
    )


@router.post("/{flow_id}/events", response_model=FlowEventResponse, status_code=201)
async def create_flow_event(
    flow_id: UUID,
    event: FlowEventCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventResponse:
    """Append an event to a flow's event queue."""
    await _verify_flow_owner(session, flow_id, current_user.id)
    e = service.append(str(flow_id), event.type, event.summary)
    return FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary)
