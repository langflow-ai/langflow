from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import paginate
from sqlalchemy import delete
from sqlmodel import col, select

from langflow.api.utils import DbSession, custom_params
from langflow.schema.message import MessageResponse
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.message.model import MessageRead, MessageTable, MessageUpdate
from langflow.services.database.models.transactions.crud import transform_transaction_table
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.crud import (
    delete_vertex_builds_by_flow_id,
    get_vertex_builds_by_flow_id,
)
from langflow.services.database.models.vertex_builds.model import VertexBuildMapModel

router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get("/builds")
async def get_vertex_builds(flow_id: Annotated[UUID, Query()], session: DbSession) -> VertexBuildMapModel:
    try:
        vertex_builds = await get_vertex_builds_by_flow_id(session, flow_id)
        return VertexBuildMapModel.from_list_of_dicts(vertex_builds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/builds", status_code=204)
async def delete_vertex_builds(flow_id: Annotated[UUID, Query()], session: DbSession) -> None:
    try:
        await delete_vertex_builds_by_flow_id(session, flow_id)
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages")
async def get_messages(
    session: DbSession,
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    sender: Annotated[str | None, Query()] = None,
    sender_name: Annotated[str | None, Query()] = None,
    order_by: Annotated[str | None, Query()] = "timestamp",
) -> list[MessageResponse]:
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
        messages = await session.exec(stmt)
        return [MessageResponse.model_validate(d, from_attributes=True) for d in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_messages(message_ids: list[UUID], session: DbSession) -> None:
    try:
        await session.exec(delete(MessageTable).where(MessageTable.id.in_(message_ids)))  # type: ignore[attr-defined]
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/messages/{message_id}", dependencies=[Depends(get_current_active_user)], response_model=MessageRead)
async def update_message(
    message_id: UUID,
    message: MessageUpdate,
    session: DbSession,
):
    try:
        db_message = await session.get(MessageTable, message_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not db_message:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        if "text" in message_dict and message_dict["text"] != db_message.text:
            message_dict["edit"] = True
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        await session.commit()
        await session.refresh(db_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return db_message


@router.patch(
    "/messages/session/{old_session_id}",
    dependencies=[Depends(get_current_active_user)],
)
async def update_session_id(
    old_session_id: str,
    new_session_id: Annotated[str, Query(..., description="The new session ID to update to")],
    session: DbSession,
) -> list[MessageResponse]:
    try:
        # Get all messages with the old session ID
        stmt = select(MessageTable).where(MessageTable.session_id == old_session_id)
        messages = (await session.exec(stmt)).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found with the given session ID")

    try:
        # Update all messages with the new session ID
        for message in messages:
            message.session_id = new_session_id

        session.add_all(messages)

        await session.commit()
        message_responses = []
        for message in messages:
            await session.refresh(message)
            message_responses.append(MessageResponse.model_validate(message, from_attributes=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return message_responses


@router.delete("/messages/session/{session_id}", status_code=204)
async def delete_messages_session(
    session_id: str,
    session: DbSession,
):
    try:
        await session.exec(
            delete(MessageTable)
            .where(col(MessageTable.session_id) == session_id)
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"message": "Messages deleted successfully"}


@router.get("/transactions")
async def get_transactions(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    params: Annotated[Params | None, Depends(custom_params)],
) -> Page[TransactionTable]:
    try:
        stmt = (
            select(TransactionTable)
            .where(TransactionTable.flow_id == flow_id)
            .order_by(col(TransactionTable.timestamp))
        )
        return await paginate(session, stmt, params=params, transformer=transform_transaction_table)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
