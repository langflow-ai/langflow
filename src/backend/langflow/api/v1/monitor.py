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
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    return monitor_service.get_vertex_builds(flow_id=flow_id, vertex_id=vertex_id, valid=valid)
