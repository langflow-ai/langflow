import asyncio
import json
from collections.abc import Sequence
from contextlib import asynccontextmanager, nullcontext, suppress
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from lfx.log.logger import logger
from lfx.memory.flow_context import is_evals_memory_isolated
from lfx.memory.session_state import SUMMARY_FIELDS, SessionMemoryState
from lfx.utils.async_helpers import run_until_complete
from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.schema.message import Message
from langflow.services.database.models.message.model import (
    ALLOWED_MESSAGE_ORDER_FIELDS,
    MessageRead,
    MessageTable,
)
from langflow.services.database.models.session_memory.model import SessionMemoryStateTable
from langflow.services.deps import session_scope


def _message_scope(
    flow_id: str | UUID | None,
    user_id: str | UUID | None,
) -> tuple[UUID | None, UUID | None]:
    """Resolve both message predicates without letting a graph caller widen them."""
    from lfx.memory.flow_context import (
        coerce_flow_id,
        get_current_flow_id,
        get_current_message_executor_id,
        get_current_message_owner_id,
        has_current_flow_scope,
    )

    requested_flow = coerce_flow_id(flow_id)
    requested_owner = coerce_flow_id(user_id)
    if has_current_flow_scope():
        graph_flow = coerce_flow_id(get_current_flow_id())
        graph_owner = get_current_message_owner_id()
        if graph_flow is None or graph_owner is None:
            return None, None
        # Saved Message Store components pass graph.user_id (the service account)
        # even when an identified serving run's message owner is its end user.
        # Treat only that trusted executor ID as a legacy hint, then query the
        # effective owner. Arbitrary supplied identities still fail closed.
        legacy_executor = get_current_message_executor_id()
        owner_matches = (
            user_id is None
            or requested_owner == graph_owner
            or (requested_owner is not None and requested_owner == legacy_executor)
        )
        if (flow_id is not None and requested_flow != graph_flow) or not owner_matches:
            return None, None
        return graph_flow, graph_owner
    return requested_flow, requested_owner


def _write_message_scope(
    flow_id: str | UUID | None,
    user_id: str | UUID | None,
) -> tuple[str | UUID | None, str | UUID | None]:
    """Stamp graph writes with the trusted flow and owner, including frozen legacy code."""
    from lfx.memory.flow_context import has_current_flow_scope

    if not has_current_flow_scope():
        return flow_id, user_id
    trusted_flow, trusted_owner = _message_scope(flow_id, user_id)
    if trusted_flow is None or trusted_owner is None:
        msg = "A valid matching flow and message owner are required to store chat history."
        raise ValueError(msg)
    return trusted_flow, trusted_owner


def _bound_message_scope() -> tuple[UUID, UUID] | None:
    """Return the graph's required scope, or None for a trusted non-graph caller."""
    from lfx.memory.flow_context import has_current_flow_scope

    if not has_current_flow_scope():
        return None
    flow_id, user_id = _message_scope(None, None)
    if flow_id is None or user_id is None:
        msg = "A valid flow and message owner are required for graph message operations."
        raise ValueError(msg)
    return flow_id, user_id


async def _validate_message_executor(session: AsyncSession) -> None:
    from lfx.memory.flow_context import (
        get_current_message_execution_principal,
        get_current_message_executor_id,
        has_current_flow_scope,
    )

    if has_current_flow_scope():
        from langflow.services.deps import get_auth_service

        await get_auth_service().validate_execution_user(
            get_current_message_executor_id(), principal=get_current_message_execution_principal(), db=session
        )


def _get_variable_query(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | UUID | None = None,
    context_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: str | UUID | None = None,
    limit: int | None = None,
    user_id: str | UUID | None = None,
):
    stmt = select(MessageTable).where(MessageTable.error == False)  # noqa: E712
    if sender:
        stmt = stmt.where(MessageTable.sender == sender)
    if sender_name:
        stmt = stmt.where(MessageTable.sender_name == sender_name)
    if session_id:
        stmt = stmt.where(MessageTable.session_id == session_id)
    if context_id:
        stmt = stmt.where(MessageTable.context_id == context_id)
    if flow_id:
        stmt = stmt.where(MessageTable.flow_id == flow_id)
    if user_id:
        # Runtime callers (e.g. _safe_graph_user_id -> graph.user_id) supply user_id as a str,
        # but MessageTable.user_id is UUID-typed: on SQLite the Uuid bind processor calls
        # ``value.hex`` and raises ``'str' object has no attribute 'hex'`` for a raw string.
        # Coerce to UUID so the owner predicate is built consistently with the write path
        # (MessageTable.from_message), rather than crashing authenticated retrieval.
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError as exc:
                msg = f"User ID {user_id} is not a valid UUID"
                raise ValueError(msg) from exc
        stmt = stmt.where(MessageTable.user_id == user_id)
    if order_by:
        if order_by not in ALLOWED_MESSAGE_ORDER_FIELDS:
            msg = f"Invalid order_by field: {order_by}"
            raise ValueError(msg)
        col = getattr(MessageTable, order_by).desc() if order == "DESC" else getattr(MessageTable, order_by).asc()
        stmt = stmt.order_by(col)
        if order_by == "timestamp":
            # Only makes the order of exact-timestamp ties deterministic (it was undefined before).
            id_col = MessageTable.id.desc() if order == "DESC" else MessageTable.id.asc()
            stmt = stmt.order_by(id_col)
    if limit:
        stmt = stmt.limit(limit)
    return stmt


def get_messages(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | UUID | None = None,
    context_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: str | UUID | None = None,
    limit: int | None = None,
    user_id: str | UUID | None = None,
) -> list[Message]:
    """DEPRECATED - Retrieves messages from the monitor service based on the provided filters.

    DEPRECATED: Use `aget_messages` instead.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        context_id (Optional[str]): The context ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        order (Optional[str]): The order in which to retrieve the messages. Defaults to "DESC".
        flow_id (Optional[UUID]): The flow ID associated with the messages.
        limit (Optional[int]): The maximum number of messages to retrieve.
        user_id (Optional[str | UUID]): Message owner; required with flow_id outside a graph.

    Returns:
        List[Data]: A list of Data objects representing the retrieved messages.
    """
    if is_evals_memory_isolated():
        return []
    return run_until_complete(
        aget_messages(
            sender,
            sender_name,
            session_id,
            context_id,
            order_by,
            order,
            flow_id,
            limit,
            user_id=user_id,
        )
    )


async def aget_messages(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | UUID | None = None,
    context_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: str | UUID | None = None,
    limit: int | None = None,
    user_id: str | UUID | None = None,
) -> list[Message]:
    """Retrieves messages from the monitor service based on the provided filters.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        context_id (Optional[str]): The context ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        order (Optional[str]): The order in which to retrieve the messages. Defaults to "DESC".
        flow_id (Optional[UUID]): The flow ID associated with the messages.
        limit (Optional[int]): The maximum number of messages to retrieve.
        user_id (Optional[str | UUID]): Message owner; required with flow_id outside a graph.

    Returns:
        List[Data]: A list of Data objects representing the retrieved messages.
    """
    if is_evals_memory_isolated():
        return []
    # Session and context IDs are caller-controlled and may collide across users.
    # Frozen saved components also call this function without either scope.
    flow_id, user_id = _message_scope(flow_id, user_id)
    if flow_id is None or user_id is None:
        return []
    async with session_scope() as session:
        stmt = _get_variable_query(
            sender, sender_name, session_id, context_id, order_by, order, flow_id, limit, user_id=user_id
        )
        messages = await session.exec(stmt)
        return [await Message.create(**d.model_dump()) for d in messages]


def add_messages(
    messages: Message | list[Message],
    flow_id: str | UUID | None = None,
    run_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
):
    """DEPRECATED - Add a message to the monitor service.

    DEPRECATED: Use `aadd_messages` instead.
    """
    return run_until_complete(aadd_messages(messages, flow_id=flow_id, run_id=run_id, user_id=user_id))


async def aadd_messages(
    messages: Message | list[Message],
    flow_id: str | UUID | None = None,
    run_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
):
    """Add a message to the monitor service."""
    if not isinstance(messages, list):
        messages = [messages]

    # Check if all messages are Message instances (either from langflow or lfx)
    for message in messages:
        # Accept Message instances from both langflow and lfx packages
        is_valid_message = isinstance(message, Message) or (
            hasattr(message, "__class__") and message.__class__.__name__ in ["Message", "ErrorMessage"]
        )
        if not is_valid_message:
            types = ", ".join([str(type(msg)) for msg in messages])
            msg = f"The messages must be instances of Message. Found: {types}"
            raise ValueError(msg)

    flow_id, user_id = _write_message_scope(flow_id, user_id)
    try:
        messages_models = [
            MessageTable.from_message(msg, flow_id=flow_id, run_id=run_id, user_id=user_id) for msg in messages
        ]
        async with session_scope() as session:
            messages_models = await aadd_messagetables(messages_models, session)
        return [await Message.create(**message.model_dump()) for message in messages_models]
    except Exception as e:
        await logger.aexception(e)
        raise


async def aupdate_messages(messages: Message | list[Message]) -> list[Message]:
    if not isinstance(messages, list):
        messages = [messages]
    graph_scope = _bound_message_scope()

    async with session_scope() as session:
        await _validate_message_executor(session)
        updated_messages: list[MessageTable] = []
        for message in messages:
            if graph_scope is None:
                msg = await session.get(MessageTable, message.id)
            else:
                stmt = select(MessageTable).where(
                    MessageTable.id == UUID(str(message.id)),
                    MessageTable.flow_id == graph_scope[0],
                    MessageTable.user_id == graph_scope[1],
                )
                msg = (await session.exec(stmt)).first()
            if msg:
                updates = message.model_dump(exclude_unset=True, exclude_none=True)
                if graph_scope is not None:
                    # Refuse scope changes and preserve the selected row's owner.
                    if _message_scope(updates.get("flow_id"), updates.get("user_id")) != graph_scope:
                        msg = "Message scope does not match the executing graph."
                        raise ValueError(msg)
                    updates.pop("flow_id", None)
                    updates.pop("user_id", None)
                # A bound graph run updates a message it just created, and a fold never covers
                # a message created after its history read. Skip the reset and its 3 statements.
                reset = (
                    nullcontext() if graph_scope is not None else reset_folded_memory_for_update(session, msg, updates)
                )
                async with reset:
                    msg = msg.sqlmodel_update(updates)
                    # Convert flow_id to UUID if it's a string preventing error when saving to database
                    if msg.flow_id and isinstance(msg.flow_id, str):
                        msg.flow_id = UUID(msg.flow_id)
                    result = session.add(msg)
                    if asyncio.iscoroutine(result):
                        await result
                updated_messages.append(msg)
            else:
                error_message = f"Message with id {message.id} not found"
                await logger.awarning(error_message)
                raise ValueError(error_message)

        return [MessageRead.model_validate(message, from_attributes=True) for message in updated_messages]


def _expires_on_commit(session) -> bool:
    """Whether committing drops the loaded attributes (sessions without the flag: assume it does)."""
    return bool(getattr(getattr(session, "sync_session", session), "expire_on_commit", True))


async def aadd_messagetables(messages: list[MessageTable], session: AsyncSession):
    """Add messages to the database.

    Args:
        messages: List of MessageTable objects to add
        session: Database session
    """
    try:
        await _validate_message_executor(session)
        for message in messages:
            result = session.add(message)
            if asyncio.iscoroutine(result):
                await result
        await session.commit()
        # Every column is set in Python before the INSERT (the id and timestamp
        # included; the table has no server-side defaults), so reading the rows
        # back would only cost a SELECT per message. A session that expires on
        # commit has dropped those values, so it still needs the refresh.
        if _expires_on_commit(session):
            for message in messages:
                await session.refresh(message)
    except asyncio.CancelledError:
        try:
            await session.rollback()
        except Exception as rollback_error:  # noqa: BLE001
            with suppress(Exception):
                await logger.aexception(
                    "Failed to roll back session after add-message cancellation",
                    error=str(rollback_error),
                )
        raise
    except Exception as e:
        await logger.aexception(e)
        raise

    new_messages = []
    for msg in messages:
        # Assign only what needs converting: each assignment marks the row dirty,
        # and the caller's commit then checks out a connection to flush a no-op.
        if isinstance(msg.properties, str):
            msg.properties = json.loads(msg.properties)
        if any(isinstance(j, str) for j in msg.content_blocks):
            msg.content_blocks = [json.loads(j) if isinstance(j, str) else j for j in msg.content_blocks]  # type: ignore[arg-type]
        if msg.category is None:
            msg.category = ""
        new_messages.append(msg)

    return [MessageRead.model_validate(message, from_attributes=True) for message in new_messages]


def delete_messages(
    session_id: str | None = None,
    context_id: str | None = None,
    *,
    flow_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> None:
    """DEPRECATED - Delete messages from the monitor service based on the provided session ID.

    DEPRECATED: Use `adelete_messages` instead.

    Args:
        session_id (str): The session ID associated with the messages to delete.
        context_id (str): The context ID associated with the messages to delete.
        flow_id (str | UUID): The trusted flow scope outside a graph run.
        user_id (str | UUID): The trusted message owner outside a graph run.
    """
    return run_until_complete(adelete_messages(session_id, context_id, flow_id=flow_id, user_id=user_id))


async def adelete_messages(
    session_id: str | None = None,
    context_id: str | None = None,
    *,
    flow_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> None:
    """Delete messages from the monitor service based on the provided session ID.

    Args:
        session_id (str): The session ID associated with the messages to delete.
        context_id (str): The context ID associated with the messages to delete.
        flow_id (str | UUID): The trusted flow scope outside a graph run.
        user_id (str | UUID): The trusted message owner outside a graph run.
    """
    if not session_id and not context_id:
        msg = "Either session_id or context_id must be provided to delete messages."
        raise ValueError(msg)
    flow_id, user_id = _message_scope(flow_id, user_id)
    if flow_id is None or user_id is None:
        msg = "A valid flow and message owner are required to delete chat history."
        raise ValueError(msg)

    async with session_scope() as session:
        # Determine which field to filter by
        filter_column = MessageTable.context_id if context_id else MessageTable.session_id
        filter_value = context_id if context_id else session_id
        scope = (col(filter_column) == filter_value, MessageTable.flow_id == flow_id, MessageTable.user_id == user_id)

        async with reset_folded_session_memory(session, *scope):
            await session.exec(delete(MessageTable).where(*scope).execution_options(synchronize_session="fetch"))


async def delete_message(id_: str) -> None:
    """Delete a message from the monitor service based on the provided ID.

    Args:
        id_ (str): The ID of the message to delete.
    """
    from lfx.memory.flow_context import should_persist_messages

    # An ephemeral message ID exists only for stream correlation, not in the DB.
    if not should_persist_messages():
        return

    graph_scope = _bound_message_scope()
    async with session_scope() as session:
        if graph_scope is None:
            message = await session.get(MessageTable, id_)
        else:
            stmt = select(MessageTable).where(
                MessageTable.id == UUID(str(id_)),
                MessageTable.flow_id == graph_scope[0],
                MessageTable.user_id == graph_scope[1],
            )
            message = (await session.exec(stmt)).first()
        if message:
            async with reset_folded_session_memory(session, MessageTable.id == message.id):
                await session.delete(message)


def store_message(
    message: Message,
    flow_id: str | UUID | None = None,
    run_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> list[Message]:
    """DEPRECATED: Stores a message in the memory.

    DEPRECATED: Use `astore_message` instead.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str | UUID]): The flow ID associated with the message.
            When running from the CustomComponent you can access this using `self.graph.flow_id`.
        run_id (Optional[str | UUID]): The graph/native run ID associated with the message.
        user_id (Optional[str | UUID]): The executing user's ID, stamped on the stored message.

    Returns:
        List[Message]: A list of data containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    return run_until_complete(astore_message(message, flow_id=flow_id, run_id=run_id, user_id=user_id))


async def astore_message(
    message: Message,
    flow_id: str | UUID | None = None,
    run_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
) -> list[Message]:
    """Stores a message in the memory.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str]): The flow ID associated with the message.
            When running from the CustomComponent you can access this using `self.graph.flow_id`.
        run_id (Optional[str | UUID]): The graph/native run ID associated with the message.
        user_id (Optional[str | UUID]): The executing user's ID, stamped on the stored message.

    Returns:
        List[Message]: A list of data containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    if not message:
        await logger.awarning("No message provided.")
        return []

    # Serving-plane ephemeral runs (anonymous end-user) must not persist chat
    # memory. The flag is bound per component execution in get_instance_results
    # from graph.persist_messages, so this is a no-op for every normal run (the
    # default is True) and returns the message unpersisted for an anonymous one.
    from lfx.memory.flow_context import has_current_flow_scope, should_persist_messages

    if not should_persist_messages():
        return [message]
    if not message.session_id or not message.sender or not message.sender_name:
        msg = (
            f"All of session_id, sender, and sender_name must be provided. Session ID: {message.session_id},"
            f" Sender: {message.sender}, Sender Name: {message.sender_name}"
        )
        raise ValueError(msg)
    flow_id, user_id = _write_message_scope(flow_id, user_id)
    if hasattr(message, "id") and message.id:
        # An existing ID may come from a nested flow's Chat Output. Its parent
        # must get a fresh row, while the child row remains untouched.
        in_graph = has_current_flow_scope()
        copy_from_child = False
        if in_graph:
            async with session_scope() as session:
                original = await session.get(MessageTable, UUID(str(message.id)))
                copy_from_child = (
                    original is not None
                    and original.flow_id is not None
                    and original.flow_id != flow_id
                    and original.user_id == user_id
                )
        # Inside a graph, unknown and different-owner IDs use the scoped
        # update path and produce the same not-found error. Outside a graph,
        # trusted callers retain the legacy missing-ID insert behavior.
        if not copy_from_child:
            try:
                return await aupdate_messages([message])
            except ValueError:
                if in_graph:
                    raise
    if flow_id and not isinstance(flow_id, UUID):
        flow_id = UUID(flow_id)
    return await aadd_messages([message], flow_id=flow_id, run_id=run_id, user_id=user_id)


class LCBuiltinChatMemory(BaseChatMessageHistory):
    """DEPRECATED: Kept for backward compatibility."""

    def __init__(
        self,
        flow_id: str,
        session_id: str,
        context_id: str | None = None,
        user_id: str | UUID | None = None,
    ) -> None:
        self.flow_id = UUID(str(flow_id))
        self.session_id = session_id
        self.context_id = context_id
        self.user_id = user_id

    def _require_scope(self) -> tuple[UUID, UUID]:
        from lfx.memory.flow_context import (
            coerce_flow_id,
            get_current_flow_id,
            get_current_message_owner_id,
            has_current_flow_scope,
        )

        flow_id = coerce_flow_id(get_current_flow_id())
        user_id = get_current_message_owner_id()
        if (
            not has_current_flow_scope()
            or flow_id is None
            or user_id is None
            or coerce_flow_id(self.flow_id) != flow_id
        ):
            msg = "Chat memory requires the executing flow and message owner."
            raise ValueError(msg)
        return flow_id, user_id

    @property
    def messages(self) -> list[BaseMessage]:
        flow_id, user_id = self._require_scope()
        messages = get_messages(
            session_id=self.session_id,
            context_id=self.context_id,
            flow_id=flow_id,
            user_id=user_id,
        )
        return [m.to_lc_message() for m in messages if not m.error]  # Exclude error messages

    async def aget_messages(self) -> list[BaseMessage]:
        flow_id, user_id = self._require_scope()
        messages = await aget_messages(
            session_id=self.session_id,
            context_id=self.context_id,
            flow_id=flow_id,
            user_id=user_id,
        )
        return [m.to_lc_message() for m in messages if not m.error]  # Exclude error messages

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        flow_id, user_id = self._require_scope()
        for lc_message in messages:
            message = Message.from_lc_message(lc_message)
            message.session_id = self.session_id
            message.context_id = self.context_id
            store_message(message, flow_id=flow_id, user_id=user_id)

    async def aadd_messages(self, messages: Sequence[BaseMessage]) -> None:
        flow_id, user_id = self._require_scope()
        for lc_message in messages:
            message = Message.from_lc_message(lc_message)
            message.session_id = self.session_id
            message.context_id = self.context_id
            await astore_message(message, flow_id=flow_id, user_id=user_id)

    def clear(self) -> None:
        flow_id, user_id = self._require_scope()
        delete_messages(self.session_id, self.context_id, flow_id=flow_id, user_id=user_id)

    async def aclear(self) -> None:
        flow_id, user_id = self._require_scope()
        await adelete_messages(self.session_id, self.context_id, flow_id=flow_id, user_id=user_id)


def _session_memory_scope_filters(flow_id: UUID, user_id: UUID, session_id: str, context_id: str | None):
    """Predicates identifying one session-memory row; ``None`` context is stored as ``""``."""
    return (
        SessionMemoryStateTable.flow_id == flow_id,
        SessionMemoryStateTable.user_id == user_id,
        SessionMemoryStateTable.session_id == session_id,
        SessionMemoryStateTable.context_id == (context_id or ""),
    )


def _to_session_memory_state(row: SessionMemoryStateTable) -> SessionMemoryState:
    return SessionMemoryState(
        id=row.id,
        summary=row.summary,
        cursor_message_id=row.cursor_message_id,
        cursor_timestamp=row.cursor_timestamp,
        folded_count=row.folded_count,
        version=row.version,
    )


async def aget_session_memory_state(
    *,
    flow_id: UUID | str | None,
    user_id: UUID | str | None,
    session_id: str,
    context_id: str | None,
) -> SessionMemoryState | None:
    """Return the stored summary state for a session, or an empty (version 0) state when none exists.

    Returns None (summaries unsupported) while Evals memory isolation is on.
    """
    if is_evals_memory_isolated():
        return None
    flow_id, user_id = _message_scope(flow_id, user_id)
    if flow_id is None or user_id is None:
        return SessionMemoryState()
    async with session_scope() as session:
        row = (
            await session.exec(
                select(SessionMemoryStateTable).where(
                    *_session_memory_scope_filters(flow_id, user_id, session_id, context_id)
                )
            )
        ).first()
        return _to_session_memory_state(row) if row else SessionMemoryState()


def _normalized(value):
    return "" if value is None else value


async def _batch_timestamps(
    session: AsyncSession,
    expected: dict[UUID, dict],
    flow_id: UUID,
    user_id: UUID,
    session_id: str,
    *,
    lock: bool,
) -> dict[UUID, datetime] | None:
    """Timestamps of the batch rows when all still exist in scope with the snapshotted `SUMMARY_FIELDS`, else None."""
    stmt = select(MessageTable.id, MessageTable.timestamp, *(getattr(MessageTable, f) for f in SUMMARY_FIELDS)).where(
        col(MessageTable.id).in_(list(expected)),
        MessageTable.flow_id == flow_id,
        MessageTable.user_id == user_id,
        MessageTable.session_id == session_id,
    )
    rows = (await session.exec(stmt.with_for_update() if lock else stmt)).all()
    current = {row[0]: row for row in rows}
    for key, snapshot in expected.items():
        row = current.get(key)
        if row is None or any(
            _normalized(row[2 + i]) != _normalized(snapshot.get(field)) for i, field in enumerate(SUMMARY_FIELDS)
        ):
            return None
    return {key: row[1] for key, row in current.items()}


async def asave_session_memory_state(
    *,
    flow_id: UUID | str | None,
    user_id: UUID | str | None,
    session_id: str,
    context_id: str | None,
    summary: str,
    cursor_message_id: UUID | str,
    folded_delta: int,
    summary_model: str | None,
    expected_version: int,
    batch_snapshot: dict[UUID | str, dict],
    expected_state_id: UUID | None = None,
) -> SessionMemoryState | None:
    """Compare-and-swap save of the summary state; returns None when the save lost a race or the batch changed.

    ``batch_snapshot`` maps each folded message id to its `SUMMARY_FIELDS` as they were summarized. The rows
    are read with ``FOR UPDATE`` first (message locks before the state write, like edits and deletes), and
    must all still exist in this session with the same values. SQLite ignores ``FOR UPDATE`` and a plain read
    opens no transaction, so the same check runs again after the write, while this transaction holds the
    write lock; if it fails, the save is rolled back. ``expected_version == 0`` inserts the first row;
    otherwise a single conditional UPDATE only succeeds while the stored ``id`` and ``version`` both match
    (a reset row that was re-created has a new id). The cursor timestamp is read from the cursor message row so
    it keeps the database's full precision. Like message writes, it needs a valid executor, and it never writes
    while Evals memory isolation is on.
    """
    if is_evals_memory_isolated():
        return None
    flow_id, user_id = _message_scope(flow_id, user_id)
    if flow_id is None or user_id is None:
        return None
    cursor_id = UUID(str(cursor_message_id))
    scope = _session_memory_scope_filters(flow_id, user_id, session_id, context_id)
    expected = {UUID(str(key)): snapshot for key, snapshot in batch_snapshot.items()}
    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        await _validate_message_executor(session)
        timestamps = await _batch_timestamps(session, expected, flow_id, user_id, session_id, lock=True)
        if timestamps is None or cursor_id not in timestamps:
            return None  # a folded message was deleted or edited while the summary was written
        cursor_timestamp = timestamps[cursor_id]
        if expected_version == 0:
            row = SessionMemoryStateTable(
                flow_id=flow_id,
                user_id=user_id,
                session_id=session_id,
                context_id=context_id or "",
                summary=summary,
                cursor_message_id=cursor_id,
                cursor_timestamp=cursor_timestamp,
                folded_count=folded_delta,
                summary_model=summary_model,
                version=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            try:
                await session.flush()
            except IntegrityError:
                # Another run created the row first; leave the session usable and report the lost race.
                await session.rollback()
                return None
        else:
            result = await session.exec(
                update(SessionMemoryStateTable)
                .where(
                    *scope,
                    SessionMemoryStateTable.id == expected_state_id,
                    SessionMemoryStateTable.version == expected_version,
                )
                .values(
                    version=expected_version + 1,
                    summary=summary,
                    cursor_message_id=cursor_id,
                    cursor_timestamp=cursor_timestamp,
                    folded_count=SessionMemoryStateTable.folded_count + folded_delta,
                    summary_model=summary_model,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 0:
                return None
            row = (await session.exec(select(SessionMemoryStateTable).where(*scope))).one()
        if await _batch_timestamps(session, expected, flow_id, user_id, session_id, lock=False) is None:
            await session.rollback()
            return None
        return _to_session_memory_state(row)


async def aget_messages_between(
    *,
    flow_id: UUID | str | None,
    user_id: UUID | str | None,
    session_id: str,
    context_id: str | None,
    after_message_id: UUID | str | None,
    after_timestamp: datetime | None,
    before_message_id: UUID | str,
    limit: int,
    newest_first: bool = False,
) -> list[Message]:
    """Return non-error messages strictly between two cursors, oldest first.

    With ``newest_first``, ``limit`` keeps the newest messages instead of the oldest. The result is still
    oldest first.

    Bounds are compared as ``(timestamp, id)`` tuples using the database's own values (a message's
    string timestamp may have lost sub-second precision). The lower bound is the stored cursor pair
    (``after_timestamp``, ``after_message_id``), so it still works after the cursor message is deleted;
    without both, the range is open below.
    Returns nothing while Evals memory isolation is on.
    """
    if is_evals_memory_isolated():
        return []
    flow_id, user_id = _message_scope(flow_id, user_id)
    if flow_id is None or user_id is None:
        return []
    async with session_scope() as session:
        boundary = (
            await session.exec(
                select(MessageTable.timestamp, MessageTable.id).where(MessageTable.id == UUID(str(before_message_id)))
            )
        ).first()
        if boundary is None:
            return []
        before_ts, before_id = boundary
        stmt = (
            select(MessageTable)
            .where(
                MessageTable.flow_id == flow_id,
                MessageTable.user_id == user_id,
                MessageTable.session_id == session_id,
                MessageTable.error == False,  # noqa: E712
                # category is nullable: NULL rows are normal messages.
                or_(col(MessageTable.category).is_(None), MessageTable.category != "error"),
                or_(
                    col(MessageTable.timestamp) < before_ts,
                    and_(col(MessageTable.timestamp) == before_ts, col(MessageTable.id) < before_id),
                ),
            )
            .order_by(
                *(
                    (col(MessageTable.timestamp).desc(), col(MessageTable.id).desc())
                    if newest_first
                    else (col(MessageTable.timestamp).asc(), col(MessageTable.id).asc())
                )
            )
            .limit(limit)
        )
        if context_id:
            stmt = stmt.where(MessageTable.context_id == context_id)
        if after_message_id is not None and after_timestamp is not None:
            after_id = UUID(str(after_message_id))
            stmt = stmt.where(
                or_(
                    col(MessageTable.timestamp) > after_timestamp,
                    and_(col(MessageTable.timestamp) == after_timestamp, col(MessageTable.id) > after_id),
                )
            )
        rows = list(await session.exec(stmt))
        if newest_first:
            rows.reverse()
        return [await Message.create(**d.model_dump()) for d in rows]


def message_update_changes_summary(message: MessageTable, updates: dict) -> bool:
    """Whether applying ``updates`` to the stored ``message`` changes content or scope a fold depends on."""
    # str(): an update may hold a flow or owner id as a string, the row as a UUID.
    return any(
        key in updates and str(updates[key]) != str(getattr(message, key, None))
        for key in (*SUMMARY_FIELDS, "flow_id", "user_id")
    )


async def _message_groups(db: AsyncSession, *message_filters) -> list[tuple]:
    """(flow, owner, session, oldest timestamp) for each session that has matching messages."""
    rows = await db.exec(
        select(
            MessageTable.flow_id,
            MessageTable.user_id,
            MessageTable.session_id,
            func.min(MessageTable.timestamp),
        )
        .where(*message_filters, col(MessageTable.user_id).isnot(None), col(MessageTable.flow_id).isnot(None))
        .group_by(MessageTable.flow_id, MessageTable.user_id, MessageTable.session_id)
    )
    return list(rows.all())


@asynccontextmanager
async def reset_folded_session_memory(db: AsyncSession, *message_filters):
    """Wrap an edit, move or delete of the messages matched by ``message_filters``, in the caller's transaction.

    Summary state that already folded any of them is deleted, so the next turn re-folds from the start. A row
    goes when its cursor is at or after the oldest matched message of its session (equal timestamps count
    as folded: over-reset is safe). The session scopes before and after the change are both reset, so a move
    resets the old and the new session. The reset runs after the change: on PostgreSQL the change waits for
    the row lock of a fold that is saving, and the reset then sees that fold's committed state.
    """
    before = await _message_groups(db, *message_filters)
    yield
    await db.flush()
    after = await _message_groups(db, *message_filters)
    for flow_id, user_id, session_id, oldest in dict.fromkeys(before + after):
        await db.exec(
            delete(SessionMemoryStateTable)
            .where(
                SessionMemoryStateTable.flow_id == flow_id,
                SessionMemoryStateTable.user_id == user_id,
                SessionMemoryStateTable.session_id == session_id,
                col(SessionMemoryStateTable.cursor_timestamp) >= oldest,
            )
            .execution_options(synchronize_session=False)
        )


def reset_folded_memory_for_update(db: AsyncSession, message: MessageTable, updates: dict):
    """Context manager to wrap applying ``updates`` to a stored ``message``: resets summary state only if needed."""
    if not message_update_changes_summary(message, updates):
        return nullcontext()
    return reset_folded_session_memory(db, MessageTable.id == message.id)


@asynccontextmanager
async def rename_session_memory(db: AsyncSession, messages: Sequence[MessageTable], new_session_id: str):
    """Wrap renaming ``messages`` to ``new_session_id``: the summary state follows, in the same transaction.

    The state is updated after the messages (same lock order as a fold). When the new session already has
    messages, the merged order is unknown, so the state is dropped and re-folded instead of moved.
    """
    if not messages:
        yield
        return
    old_session_id = messages[0].session_id
    scopes = {(m.flow_id, m.user_id) for m in messages if m.flow_id and m.user_id}
    merging = {}
    for flow_id, user_id in scopes:
        existing = await db.exec(
            select(MessageTable.id)
            .where(
                MessageTable.flow_id == flow_id,
                MessageTable.user_id == user_id,
                MessageTable.session_id == new_session_id,
            )
            .limit(1)
        )
        merging[flow_id, user_id] = existing.first() is not None
    yield
    await db.flush()
    for flow_id, user_id in scopes:
        scope = (SessionMemoryStateTable.flow_id == flow_id, SessionMemoryStateTable.user_id == user_id)
        # A stale row at the destination would break the unique scope.
        await db.exec(
            delete(SessionMemoryStateTable).where(*scope, SessionMemoryStateTable.session_id == new_session_id)
        )
        old_rows = SessionMemoryStateTable.session_id == old_session_id
        if merging[flow_id, user_id]:
            await db.exec(delete(SessionMemoryStateTable).where(*scope, old_rows))
        else:
            await db.exec(
                update(SessionMemoryStateTable)
                .where(*scope, old_rows)
                .values(session_id=new_session_id)
                .execution_options(synchronize_session=False)
            )
