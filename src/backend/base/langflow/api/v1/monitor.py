from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from langflow.services.deps import get_monitor_service
from langflow.services.monitor.schema import (
    MessageModelRequest,
    MessageModelResponse,
    TransactionModelResponse,
    VertexBuildMapModel,
)
from langflow.services.monitor.service import MonitorService

router = APIRouter(prefix="/monitor", tags=["Monitor"])


# Get vertex_builds data from the monitor service
@router.get("/builds", response_model=VertexBuildMapModel)
async def get_vertex_builds(
    flow_id: Optional[str] = Query(None),
    vertex_id: Optional[str] = Query(None),
    valid: Optional[bool] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        vertex_build_dicts = monitor_service.get_vertex_builds(
            flow_id=flow_id, vertex_id=vertex_id, valid=valid, order_by=order_by
        )
        vertex_build_map = VertexBuildMapModel.from_list_of_dicts(vertex_build_dicts)
        return vertex_build_map
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/builds", status_code=204)
async def delete_vertex_builds(
    flow_id: Optional[str] = Query(None),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        monitor_service.delete_vertex_builds(flow_id=flow_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=List[MessageModelResponse])
async def get_messages(
    flow_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    sender_name: Optional[str] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        df = monitor_service.get_messages(
            flow_id=flow_id,
            sender=sender,
            sender_name=sender_name,
            session_id=session_id,
            order_by=order_by,
        )
        dicts = df.to_dict(orient="records")
        return [MessageModelResponse(**d) for d in dicts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages", status_code=204)
async def delete_messages(
    message_ids: List[int],
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        monitor_service.delete_messages(message_ids=message_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages/{message_id}", response_model=MessageModelResponse)
async def update_message(
    message_id: str,
    message: MessageModelRequest,
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        message_dict = message.model_dump(exclude_none=True)
        message_dict.pop("index", None)
        monitor_service.update_message(message_id=message_id, **message_dict)
        return MessageModelResponse(index=message_id, **message_dict)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages/session/{session_id}", status_code=204)
async def delete_messages_session(
    session_id: str,
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        monitor_service.delete_messages_session(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=List[TransactionModelResponse])
async def get_transactions(
    source: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    order_by: Optional[str] = Query("timestamp"),
    flow_id: Optional[str] = Query(None),
    monitor_service: MonitorService = Depends(get_monitor_service),
):
    try:
        dicts = monitor_service.get_transactions(
            source=source, target=target, status=status, order_by=order_by, flow_id=flow_id
        )
        return [TransactionModelResponse(**d) for d in dicts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
