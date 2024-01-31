from typing import Optional

from fastapi import APIRouter, Depends, Query

from langflow.services.deps import get_monitor_service
from langflow.services.monitor.schema import VertexBuildModel
from langflow.services.monitor.service import MonitorService

router = APIRouter(prefix="/monitor", tags=["Monitor"])


# Get vertex_builds data from the monitor service
@router.get("/builds", response_model=list[VertexBuildModel])
async def get_vertex_builds(
    flow_id: Optional[str] = Query(None),
    vertex_id: Optional[str] = Query(None),
    valid: Optional[bool] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    return monitor_service.get_vertex_builds(flow_id=flow_id, vertex_id=vertex_id, valid=valid, order_by=order_by)


@router.get("/messages")
async def get_messages(
    session_id: Optional[str] = Query(None),
    sender_type: Optional[str] = Query(None),
    sender_name: Optional[str] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    return monitor_service.get_messages(
        sender_type=sender_type, sender_name=sender_name, session_id=session_id, order_by=order_by
    )


@router.get("/transactions")
async def get_transactions(
    source: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    return monitor_service.get_transactions(source=source, target=target, status=status, order_by=order_by)
