import asyncio
import json
from collections.abc import Sequence
from contextlib import suppress
from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from lfx.log.logger import logger
from lfx.utils.async_helpers import run_until_complete
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.schema.message import Message
from langflow.services.database.models.message.model import (
    ALLOWED_MESSAGE_ORDER_FIELDS,
    MessageRead,
    MessageTable,
)
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

    async with session_scope() as session:
        updated_messages: list[MessageTable] = []
        for message in messages:
            msg = await session.get(MessageTable, message.id)
            if msg:
                msg = msg.sqlmodel_update(message.model_dump(exclude_unset=True, exclude_none=True))
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


async def aadd_messagetables(messages: list[MessageTable], session: AsyncSession):
    """Add messages to the database.

    Args:
        messages: List of MessageTable objects to add
        session: Database session
    """
    try:
        for message in messages:
            result = session.add(message)
            if asyncio.iscoroutine(result):
                await result
        await session.commit()
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
        msg.properties = json.loads(msg.properties) if isinstance(msg.properties, str) else msg.properties  # type: ignore[arg-type]
        msg.content_blocks = [json.loads(j) if isinstance(j, str) else j for j in msg.content_blocks]  # type: ignore[arg-type]
        msg.category = msg.category or ""
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

        stmt = (
            delete(MessageTable)
            .where(col(filter_column) == filter_value)
            .where(MessageTable.flow_id == flow_id)
            .where(MessageTable.user_id == user_id)
            .execution_options(synchronize_session="fetch")
        )
        await session.exec(stmt)


async def delete_message(id_: str) -> None:
    """Delete a message from the monitor service based on the provided ID.

    Args:
        id_ (str): The ID of the message to delete.
    """
    async with session_scope() as session:
        message = await session.get(MessageTable, id_)
        if message:
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
    from lfx.memory.flow_context import should_persist_messages

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
        # if message has an id and exist in the database, update it
        # if not raise an error and add the message to the database
        try:
            return await aupdate_messages([message])
        except ValueError as e:
            await logger.aerror(e)
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
    ) -> None:
        self.flow_id = flow_id
        self.session_id = session_id
        self.context_id = context_id

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
