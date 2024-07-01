from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlmodel import Session, col, select

from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.message.model import MessageRead, MessageTable, MessageUpdate
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_monitor_service, get_session
from langflow.services.monitor.schema import MessageModelResponse, TransactionModelResponse, VertexBuildMapModel
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
    session: Session = Depends(get_session),
):
    try:
        stmt = select(MessageTable)
        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if session_id:
            stmt = stmt.where(MessageTable.session_id == session_id)
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if order_by:
            col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(col)
        messages = session.exec(stmt)
        return [MessageModelResponse.model_validate(d, from_attributes=True) for d in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages", status_code=204)
async def delete_messages(
    message_ids: List[UUID],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    try:
        session.exec(delete(MessageTable).where(MessageTable.id.in_(message_ids)))  # type: ignore
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/messages/{message_id}", response_model=MessageRead)
async def update_message(
    message_id: UUID,
    message: MessageUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    try:
        db_message = session.get(MessageTable, message_id)
        if not db_message:
            raise HTTPException(status_code=404, detail="Message not found")
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        session.commit()
        session.refresh(db_message)
        return db_message
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages/session/{session_id}", status_code=204)
async def delete_messages_session(
    session_id: str,
    session: Session = Depends(get_session),
):
    try:
        session.exec(  # type: ignore
            delete(MessageTable)
            .where(col(MessageTable.session_id) == session_id)
            .execution_options(synchronize_session="fetch")
        )
        session.commit()
        return {"message": "Messages deleted successfully"}
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
        result = []
        for d in dicts:
            d = TransactionModelResponse(
                index=d["index"],
                timestamp=d["timestamp"],
                vertex_id=d["vertex_id"],
                inputs=d["inputs"],
                outputs=d["outputs"],
                status=d["status"],
                error=d["error"],
                flow_id=d["flow_id"],
                source=d["vertex_id"],
                target=d["target_id"],
            )
            result.append(d)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
