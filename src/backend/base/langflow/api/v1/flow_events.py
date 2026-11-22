from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from langflow.api.v1.authz_route_dependencies import AuthorizedReadFlow, AuthorizedWriteFlow
from langflow.services.deps import get_flow_events_service
from langflow.services.flow_events import FLOW_EVENT_TYPES, FlowEventsService

router = APIRouter(prefix="/flows", tags=["Flow Events"], include_in_schema=False)


class FlowEventResponse(BaseModel):
    type: str
    timestamp: float
    summary: str


class FlowEventsResponse(BaseModel):
    events: list[FlowEventResponse]
    settled: bool


class FlowEventCreate(BaseModel):
    type: FLOW_EVENT_TYPES
    summary: str = Field(default="", max_length=500)


@router.get("/{flow_id}/events", response_model=FlowEventsResponse)
async def get_flow_events(
    flow: AuthorizedReadFlow,
    since: Annotated[float, Query(description="UTC timestamp to get events after")] = 0.0,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventsResponse:
    events, settled = service.get_since(str(flow.id), since)
    return FlowEventsResponse(
        events=[FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary) for e in events],
        settled=settled,
    )


@router.post("/{flow_id}/events", response_model=FlowEventResponse, status_code=201)
async def create_flow_event(
    flow: AuthorizedWriteFlow,
    event: FlowEventCreate,
    *,
    service: Annotated[FlowEventsService, Depends(get_flow_events_service)],
) -> FlowEventResponse:
    """Append an event to a flow's event queue."""
    e = service.append(str(flow.id), event.type, event.summary)
    return FlowEventResponse(type=e.type, timestamp=e.timestamp, summary=e.summary)
