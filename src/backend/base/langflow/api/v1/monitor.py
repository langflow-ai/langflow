from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from sqlmodel import col, delete, select

from langflow.api.utils import DbSession, custom_params
from langflow.api.utils.flow_utils import compute_virtual_flow_id
from langflow.schema.message import MessageResponse
from langflow.services.auth.utils import get_current_active_superuser, get_current_active_user
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.crud import (
    delete_messages_for_user,
    delete_messages_for_user_by_session,
    get_message_for_user,
    get_messages_for_user_by_session,
)
from langflow.services.database.models.message.model import MessageRead, MessageTable, MessageUpdate
from langflow.services.database.models.transactions.crud import transform_transaction_table_for_logs
from langflow.services.database.models.transactions.model import TransactionLogsResponse, TransactionTable
from langflow.services.database.models.user.model import User
from langflow.services.database.models.vertex_builds.crud import (
    delete_vertex_builds_by_flow_id,
    get_vertex_builds_by_flow_id,
)
from langflow.services.database.models.vertex_builds.model import VertexBuildMapModel
from langflow.services.deps import get_memory_base_service, get_tracing_service
from langflow.services.tracing.langfuse import (
    delete_feedback_score,
    langfuse_is_configured,
    normalize_langfuse_trace_id,
    sync_feedback_score,
)

router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get("/job_queue", dependencies=[Depends(get_current_active_superuser)])
async def job_queue_metrics() -> dict:
    """Return a snapshot of job-queue observability metrics.

    For the in-memory backend this exposes only ``backend`` and ``active_jobs``.
    For the Redis backend the snapshot also includes bridge counts, consumer
    wrappers, cancel-dispatcher liveness, and the cancel-stats counters
    (``published`` / ``marker_hit`` / ``dispatched_owned`` /
    ``dispatched_foreign`` / ``publish_errors`` / ``dispatcher_reconnects`` /
    ``polling_watchdog_kills`` / ``activity_touch_errors`` /
    ``activity_get_errors`` / ``activity_parse_errors`` /
    ``dispatcher_internal_errors``). ``dispatcher_reconnects`` tracks explicit
    dispatcher-loop retries and redis-py transparent pubsub reconnect callbacks.

    Restricted to superusers because the snapshot exposes process-wide tenant
    activity (live job counts, cancel rates) — useful for ops, sensitive in
    multi-tenant deployments.
    """
    from langflow.services.deps import get_queue_service

    return get_queue_service().metrics_snapshot()


def _get_positive_feedback_value(db_message: MessageTable) -> bool | None:
    properties = db_message.properties
    if hasattr(properties, "positive_feedback"):
        return properties.positive_feedback
    if isinstance(properties, dict):
        return properties.get("positive_feedback")
    return None


def _resolve_langfuse_trace_id(db_message: MessageTable) -> str | None:
    session_metadata = db_message.session_metadata or {}
    if isinstance(session_metadata, dict):
        return normalize_langfuse_trace_id(session_metadata.get("langfuse_trace_id"))
    return None


def _langfuse_feedback_sync_enabled() -> bool:
    """Check both the global tracing kill switch and Langfuse credentials.

    Used to gate background tasks so we don't enqueue work that would
    silently no-op when tracing is deactivated or Langfuse is unconfigured.
    """
    tracing_service = get_tracing_service()
    if tracing_service.deactivated:
        return False
    return langfuse_is_configured()


async def _ensure_flow_action_or_404(
    session: DbSession,
    *,
    flow_id: UUID,
    user: User,
    action: FlowAction,
) -> Flow | None:
    """Load a flow (share-aware), enforce permission, return None if missing."""
    flow = await authorized_or_owner_scoped(
        session,
        Flow,
        id_column=Flow.id,
        resource_id=flow_id,
        owner_column=Flow.user_id,
        owner_id=user.id,
    )
    if flow is None:
        return None
    await ensure_flow_permission(
        user,
        action,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=getattr(flow, "workspace_id", None),
        folder_id=getattr(flow, "folder_id", None),
    )
    return flow


async def _purge_memory_base_session_data(user_id: UUID, session_ids: list[str]) -> None:
    """Best-effort: drop ingested chunks for the deleted sessions from each MB.

    Failures here are logged but never abort the message-delete response — the
    user expects "delete this session" to succeed even if KB cleanup hits an
    issue. The follow-up consequence (ghost chunks) is logged for ops to fix.
    """
    if not session_ids:
        return
    try:
        await get_memory_base_service().purge_session_data(user_id=user_id, session_ids=session_ids)
    except Exception:  # noqa: BLE001
        # Lazy import to avoid pulling logger into the module-import path for
        # an endpoint that doesn't need it on the happy path.
        from lfx.log.logger import logger

        await logger.aerror(
            "Memory Base session purge failed for user=%s sessions=%d",
            user_id,
            len(session_ids),
            exc_info=True,
        )


@router.get("/builds", dependencies=[Depends(get_current_active_user)])
async def get_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> VertexBuildMapModel:
    try:
        # Ownership is enforced in the data access layer.
        # Foreign flow IDs intentionally resolve to an empty payload (200)
        # to avoid leaking whether the target flow exists.
        flow = await _ensure_flow_action_or_404(session, flow_id=flow_id, user=current_user, action=FlowAction.READ)
        if flow is None:
            return VertexBuildMapModel.from_list_of_dicts([])
        vertex_builds = await get_vertex_builds_by_flow_id(session, flow_id, user_id=flow.user_id)
        return VertexBuildMapModel.from_list_of_dicts(vertex_builds)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/builds", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_vertex_builds(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    try:
        # Keep endpoint idempotent while preventing cross-user deletion.
        flow = await _ensure_flow_action_or_404(session, flow_id=flow_id, user=current_user, action=FlowAction.WRITE)
        if flow is None:
            return
        await delete_vertex_builds_by_flow_id(session, flow_id, user_id=flow.user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages/sessions")
async def get_message_sessions(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    flow_id: Annotated[UUID | None, Query()] = None,
) -> list[str]:
    try:
        # When a flow_id is provided, gate on flow READ permission so a viewer
        # without flow access cannot enumerate sessions. The bulk path
        # (flow_id is None) keeps the user-scoped JOIN — share-aware listing
        # across all visible flows is an plugin optimisation.
        if flow_id is not None:
            flow = await _ensure_flow_action_or_404(session, flow_id=flow_id, user=current_user, action=FlowAction.READ)
            if flow is None:
                return []
            stmt = select(MessageTable.session_id).distinct()
            stmt = stmt.where(MessageTable.flow_id == flow_id)
            stmt = stmt.where(col(MessageTable.session_id).isnot(None))
            stmt = stmt.where(~col(MessageTable.session_id).startswith("agentic_"))
            session_ids = await session.exec(stmt)
            return list(session_ids)

        stmt = select(MessageTable.session_id).distinct()
        stmt = stmt.join(Flow, MessageTable.flow_id == Flow.id)
        stmt = stmt.where(col(MessageTable.session_id).isnot(None))
        stmt = stmt.where(~col(MessageTable.session_id).startswith("agentic_"))
        stmt = stmt.where(Flow.user_id == current_user.id)

        session_ids = await session.exec(stmt)
        return list(session_ids)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages")
async def get_messages(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    flow_id: Annotated[UUID | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    sender: Annotated[str | None, Query()] = None,
    sender_name: Annotated[str | None, Query()] = None,
    order_by: Annotated[str | None, Query()] = "timestamp",
) -> list[MessageResponse]:
    try:
        # When a flow_id is provided, gate on flow READ permission first; the
        # share-aware path lets a non-owner with a read grant see the flow's
        # messages.
        if flow_id is not None:
            flow = await _ensure_flow_action_or_404(session, flow_id=flow_id, user=current_user, action=FlowAction.READ)
            if flow is None:
                return []

        # Use JOIN instead of subquery for better performance
        stmt = select(MessageTable)
        stmt = stmt.join(Flow, MessageTable.flow_id == Flow.id)
        if flow_id is None:
            stmt = stmt.where(Flow.user_id == current_user.id)

        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if session_id:
            from urllib.parse import unquote

            decoded_session_id = unquote(session_id)
            stmt = stmt.where(MessageTable.session_id == decoded_session_id)
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if order_by:
            order_col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(order_col)
        messages = await session.exec(stmt)
        return [MessageResponse.model_validate(d, from_attributes=True) for d in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_messages(
    message_ids: list[UUID],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    try:
        # Ownership guard lives in the CRUD layer: only messages belonging to
        # current_user are selected and deleted; foreign IDs are ignored.
        #
        # Practical effect:
        # - Mixed lists (owned + foreign IDs) only delete owned rows.
        # - Pure foreign lists keep endpoint idempotent with 204 and no changes.
        await delete_messages_for_user(session, current_user.id, message_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/messages/{message_id}", dependencies=[Depends(get_current_active_user)], response_model=MessageRead)
async def update_message(
    message_id: UUID,
    message: MessageUpdate,
    session: DbSession,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        # Fetch is scoped by user ownership. A foreign message ID resolves to
        # None so callers receive the same 404 as a non-existent message.
        # This avoids leaking whether another user's message exists.
        db_message = await get_message_for_user(session, current_user.id, message_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not db_message:
        # Intentionally return 404 for both "not found" and "not owned".
        raise HTTPException(status_code=404, detail="Message not found")

    # Bind the parent flow's authorization to message writes so a viewer-role
    # user cannot edit messages on a flow they only have READ on.
    if db_message.flow_id is not None:
        await _ensure_flow_action_or_404(
            session, flow_id=db_message.flow_id, user=current_user, action=FlowAction.WRITE
        )

    try:
        previous_positive_feedback = _get_positive_feedback_value(db_message)
        message_dict = message.model_dump(exclude_unset=True, exclude_none=True)
        if "text" in message_dict and message_dict["text"] != db_message.text:
            # Keep edit flag consistent for UI/audit consumers when content changes.
            message_dict["edit"] = True
        db_message.sqlmodel_update(message_dict)
        session.add(db_message)
        await session.flush()
        await session.refresh(db_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    current_positive_feedback = _get_positive_feedback_value(db_message)
    langfuse_trace_id = _resolve_langfuse_trace_id(db_message)
    if (
        current_positive_feedback != previous_positive_feedback
        and langfuse_trace_id
        and _langfuse_feedback_sync_enabled()
    ):
        if current_positive_feedback is None:
            background_tasks.add_task(
                delete_feedback_score,
                message_id=db_message.id,
            )
        else:
            background_tasks.add_task(
                sync_feedback_score,
                message_id=db_message.id,
                trace_id=langfuse_trace_id,
                session_id=db_message.session_id,
                flow_id=db_message.flow_id,
                sender=db_message.sender,
                positive_feedback=current_positive_feedback,
            )
    return db_message


@router.patch(
    "/messages/session/{old_session_id}",
    dependencies=[Depends(get_current_active_user)],
)
async def update_session_id(
    old_session_id: str,
    new_session_id: Annotated[str, Query(..., description="The new session ID to update to")],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[MessageResponse]:
    try:
        # Session updates are ownership-scoped to prevent session hijacking
        # across users that might share or guess a session_id value.
        # This endpoint is sensitive because a single call can move many rows.
        messages = await get_messages_for_user_by_session(session, current_user.id, old_session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not messages:
        # Same response for "session does not exist" and "session exists but is foreign".
        raise HTTPException(status_code=404, detail="No messages found with the given session ID")

    try:
        # Update all messages with the new session ID
        for message in messages:
            message.session_id = new_session_id

        session.add_all(messages)

        await session.flush()
        message_responses = []
        for message in messages:
            await session.refresh(message)
            message_responses.append(MessageResponse.model_validate(message, from_attributes=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return message_responses


@router.delete("/messages/session/{session_id}", status_code=204, dependencies=[Depends(get_current_active_user)])
async def delete_messages_session(
    session_id: str,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Delete messages for a single session.

    Only deletes messages from sessions belonging to flows owned by the current user.
    """
    try:
        # Keep endpoint idempotent (204) while enforcing ownership in CRUD.
        # If the session belongs to another user, this becomes a safe no-op.
        # This preserves existing client behavior while blocking cross-user deletes.
        await delete_messages_for_user_by_session(session, current_user.id, session_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Purge ingested chunks AFTER the message rows are committed so a chunk-delete
    # failure can never roll back the user-visible message delete.
    await _purge_memory_base_session_data(current_user.id, [session_id])

    return {"message": "Messages deleted successfully"}


@router.delete("/messages/sessions", status_code=200, dependencies=[Depends(get_current_active_user)])
async def delete_messages_sessions(
    session_ids: list[str],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Bulk delete messages for multiple sessions at once.

    Only deletes messages from sessions belonging to flows owned by the current user.

    Args:
        session_ids: List of session IDs to delete (max 500)
        session: Database session
        current_user: Current authenticated user

    Returns:
        Confirmation message with count of deleted sessions

    Raises:
        HTTPException: 400 if session_ids list exceeds 500 items
        HTTPException: 500 if database operation fails
    """
    # Validate input size to prevent massive SQL IN clauses
    max_sessions_per_request = 500
    if len(session_ids) > max_sessions_per_request:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete more than {max_sessions_per_request} sessions at once. Please batch your requests.",
        )

    if not session_ids:
        return {"message": "No sessions to delete", "deleted_count": 0}

    try:
        # First, get distinct session IDs that have messages belonging to the user's flows
        session_stmt = select(MessageTable.session_id).distinct()
        session_stmt = session_stmt.join(Flow, MessageTable.flow_id == Flow.id)
        session_stmt = session_stmt.where(Flow.user_id == current_user.id)
        session_stmt = session_stmt.where(col(MessageTable.session_id).in_(session_ids))

        result = await session.exec(session_stmt)
        affected_session_ids = list(result)
        affected_count = len(affected_session_ids)

        if not affected_session_ids:
            # No messages found for this user's flows with these session_ids
            return {"message": "No sessions to delete", "deleted_count": 0}

        # Get message IDs to delete
        msg_stmt = select(MessageTable.id)
        msg_stmt = msg_stmt.join(Flow, MessageTable.flow_id == Flow.id)
        msg_stmt = msg_stmt.where(Flow.user_id == current_user.id)
        msg_stmt = msg_stmt.where(col(MessageTable.session_id).in_(affected_session_ids))

        msg_result = await session.exec(msg_stmt)
        message_ids = list(msg_result)

        # Delete only the messages that belong to the user
        await session.exec(
            delete(MessageTable)
            .where(col(MessageTable.id).in_(message_ids))
            .execution_options(synchronize_session="fetch")
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Purge ingested chunks AFTER the messages are committed; same reasoning as above.
    await _purge_memory_base_session_data(current_user.id, list(affected_session_ids))

    return {
        "message": f"Messages deleted successfully for {affected_count} session{'s' if affected_count != 1 else ''}",
        "deleted_count": affected_count,
    }


@router.get("/messages/shared/sessions")
async def get_shared_message_sessions(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    source_flow_id: Annotated[UUID, Query(description="The original public flow ID")],
) -> list[str]:
    """Get session IDs for a shared/public flow, scoped to the authenticated user.

    Uses a deterministic virtual flow_id derived from the user's ID and the
    original flow ID. Only messages stored under this virtual flow_id are returned.
    """
    try:
        virtual_flow_id = compute_virtual_flow_id(current_user.id, source_flow_id)
        stmt = select(MessageTable.session_id).distinct()
        stmt = stmt.where(MessageTable.flow_id == virtual_flow_id)
        stmt = stmt.where(col(MessageTable.session_id).isnot(None))

        session_ids = await session.exec(stmt)
        return list(session_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/messages/shared")
async def get_shared_messages(
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    source_flow_id: Annotated[UUID, Query(description="The original public flow ID")],
    session_id: Annotated[str | None, Query()] = None,
    order_by: Annotated[str | None, Query()] = "timestamp",
) -> list[MessageResponse]:
    """Get messages for a shared/public flow, scoped to the authenticated user.

    Uses a deterministic virtual flow_id derived from the user's ID and the
    original flow ID. Only messages stored under this virtual flow_id are returned.
    """
    try:
        virtual_flow_id = compute_virtual_flow_id(current_user.id, source_flow_id)
        stmt = select(MessageTable)
        stmt = stmt.where(MessageTable.flow_id == virtual_flow_id)

        if session_id:
            from urllib.parse import unquote

            decoded_session_id = unquote(session_id)
            stmt = stmt.where(MessageTable.session_id == decoded_session_id)
        allowed_order_fields = {"timestamp", "sender", "sender_name", "session_id", "text"}
        if order_by:
            if order_by not in allowed_order_fields:
                raise HTTPException(status_code=400, detail=f"Invalid order_by field: {order_by}")
            order_col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(order_col)

        messages = await session.exec(stmt)
        return [MessageResponse.model_validate(d, from_attributes=True) for d in messages]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/messages/shared/session/{session_id}", status_code=204)
async def delete_shared_messages_session(
    session_id: str,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    source_flow_id: Annotated[UUID, Query(description="The original public flow ID")],
):
    """Delete messages for a session on a shared/public flow, scoped to the authenticated user."""
    try:
        virtual_flow_id = compute_virtual_flow_id(current_user.id, source_flow_id)
        stmt = (
            delete(MessageTable)
            .where(MessageTable.flow_id == virtual_flow_id)
            .where(MessageTable.session_id == session_id)
        )
        await session.exec(stmt)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/messages/shared/{message_id}", response_model=MessageRead)
async def update_shared_message(
    message_id: UUID,
    message: MessageUpdate,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    source_flow_id: Annotated[UUID, Query(description="The original public flow ID")],
):
    """Update a message on a shared/public flow, scoped to the authenticated user."""
    try:
        virtual_flow_id = compute_virtual_flow_id(current_user.id, source_flow_id)
        db_message = (
            await session.exec(
                select(MessageTable).where(
                    MessageTable.id == message_id,
                    MessageTable.flow_id == virtual_flow_id,
                )
            )
        ).first()
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
        await session.flush()
        await session.refresh(db_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return db_message


@router.patch("/messages/shared/session/{old_session_id}")
async def rename_shared_session(
    old_session_id: str,
    new_session_id: Annotated[str, Query(description="The new session ID")],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    source_flow_id: Annotated[UUID, Query(description="The original public flow ID")],
) -> list[MessageResponse]:
    """Rename a session on a shared/public flow, scoped to the authenticated user."""
    try:
        virtual_flow_id = compute_virtual_flow_id(current_user.id, source_flow_id)
        stmt = select(MessageTable).where(
            MessageTable.flow_id == virtual_flow_id,
            MessageTable.session_id == old_session_id,
        )
        messages = list(await session.exec(stmt))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found with the given session ID")

    try:
        for message in messages:
            message.session_id = new_session_id
        session.add_all(messages)
        await session.flush()

        result = []
        for message in messages:
            await session.refresh(message)
            result.append(MessageResponse.model_validate(message, from_attributes=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return result


@router.get("/transactions", dependencies=[Depends(get_current_active_user)])
async def get_transactions(
    flow_id: Annotated[UUID, Query()],
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
    params: Annotated[Params | None, Depends(custom_params)],
) -> Page[TransactionLogsResponse]:
    try:
        # Flow ownership / share-grant is verified via the parent flow guard.
        # For foreign flow IDs, the endpoint returns an empty page (200)
        # to preserve response shape and avoid existence leakage.
        flow = await _ensure_flow_action_or_404(session, flow_id=flow_id, user=current_user, action=FlowAction.READ)
        if flow is None:
            from fastapi_pagination import Page as _Page

            return _Page(items=[], total=0, page=1, size=params.size if params else 50, pages=0)
        stmt = (
            select(TransactionTable)
            .join(Flow, TransactionTable.flow_id == Flow.id)
            .where(TransactionTable.flow_id == flow_id)
            .order_by(col(TransactionTable.timestamp).desc())
        )
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
            )
            return await apaginate(session, stmt, params=params, transformer=transform_transaction_table_for_logs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
