from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
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


@router.get("/{flow_id}/events", response_model=FlowEventsResponse)
async def get_flow_events(
    flow_id: str,
    _current_user: CurrentActiveUser,
    since: Annotated[float, Query(description="UTC timestamp to get events after")] = 0.0,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventsResponse:
    events, settled = service.get_since(flow_id, since)
    return FlowEventsResponse(
        events=[FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary) for e in events],
        settled=settled,
    )


@router.post("/{flow_id}/events", response_model=FlowEventResponse, status_code=201)
async def create_flow_event(
    flow_id: str,
    event: FlowEventCreate,
    _current_user: CurrentActiveUser,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventResponse:
    """Append an event to a flow's event queue. Called by the MCP server after mutations."""
    e = service.append(flow_id, event.type, event.summary)
    return FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary)
