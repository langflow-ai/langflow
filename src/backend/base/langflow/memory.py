import json
from collections.abc import Sequence
from uuid import UUID

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from loguru import logger
from sqlalchemy import delete
from sqlmodel import Session, col, select

from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageRead, MessageTable
from langflow.services.deps import session_scope


def get_messages(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: UUID | None = None,
    limit: int | None = None,
) -> list[Message]:
    """Retrieves messages from the monitor service based on the provided filters.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        order (Optional[str]): The order in which to retrieve the messages. Defaults to "DESC".
        flow_id (Optional[UUID]): The flow ID associated with the messages.
        limit (Optional[int]): The maximum number of messages to retrieve.

    Returns:
        List[Data]: A list of Data objects representing the retrieved messages.
    """
    with session_scope() as session:
        stmt = select(MessageTable).where(MessageTable.error == False)  # noqa: E712
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if session_id:
            stmt = stmt.where(MessageTable.session_id == session_id)
        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if order_by:
            col = getattr(MessageTable, order_by).desc() if order == "DESC" else getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(col)
        if limit:
            stmt = stmt.limit(limit)
        messages = session.exec(stmt)
        return [Message(**d.model_dump()) for d in messages]


def add_messages(messages: Message | list[Message], flow_id: str | None = None):
    """Add a message to the monitor service."""
    if not isinstance(messages, list):
        messages = [messages]

    if not all(isinstance(message, Message) for message in messages):
        types = ", ".join([str(type(message)) for message in messages])
        msg = f"The messages must be instances of Message. Found: {types}"
        raise ValueError(msg)

    try:
        messages_models = [MessageTable.from_message(msg, flow_id=flow_id) for msg in messages]
        with session_scope() as session:
            messages_models = add_messagetables(messages_models, session)
        return [Message(**message.model_dump()) for message in messages_models]
    except Exception as e:
        logger.exception(e)
        raise


def update_messages(messages: Message | list[Message]) -> list[Message]:
    if not isinstance(messages, list):
        messages = [messages]

    with session_scope() as session:
        updated_messages: list[MessageTable] = []
        for message in messages:
            msg = session.get(MessageTable, message.id)
            if msg:
                msg.sqlmodel_update(message.model_dump(exclude_unset=True, exclude_none=True))
                session.add(msg)
                session.commit()
                session.refresh(msg)
                updated_messages.append(msg)
            else:
                logger.warning(f"Message with id {message.id} not found")
        return [MessageRead.model_validate(message, from_attributes=True) for message in updated_messages]


def add_messagetables(messages: list[MessageTable], session: Session):
    for message in messages:
        try:
            session.add(message)
            session.commit()
            session.refresh(message)
        except Exception as e:
            logger.exception(e)
            raise

    new_messages = []
    for msg in messages:
        msg.properties = json.loads(msg.properties) if isinstance(msg.properties, str) else msg.properties  # type: ignore[arg-type]
        msg.content_blocks = [json.loads(j) if isinstance(j, str) else j for j in msg.content_blocks]  # type: ignore[arg-type]
        msg.category = msg.category or ""
        new_messages.append(msg)

    return [MessageRead.model_validate(message, from_attributes=True) for message in new_messages]


def delete_messages(session_id: str) -> None:
    """Delete messages from the monitor service based on the provided session ID.

    Args:
        session_id (str): The session ID associated with the messages to delete.
    """
    with session_scope() as session:
        session.exec(
            delete(MessageTable)
            .where(col(MessageTable.session_id) == session_id)
            .execution_options(synchronize_session="fetch")
        )


def delete_message(id_: str) -> None:
    """Delete a message from the monitor service based on the provided ID.

    Args:
        id_ (str): The ID of the message to delete.
    """
    with session_scope() as session:
        message = session.get(MessageTable, id_)
        if message:
            session.delete(message)
            session.commit()


def store_message(
    message: Message,
    flow_id: str | None = None,
) -> list[Message]:
    """Stores a message in the memory.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str]): The flow ID associated with the message.
            When running from the CustomComponent you can access this using `self.graph.flow_id`.

    Returns:
        List[Message]: A list of data containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    if not message:
        logger.warning("No message provided.")
        return []

    if not message.session_id or not message.sender or not message.sender_name:
        msg = "All of session_id, sender, and sender_name must be provided."
        raise ValueError(msg)
    if hasattr(message, "id") and message.id:
        return update_messages([message])
    return add_messages([message], flow_id=flow_id)


class LCBuiltinChatMemory(BaseChatMessageHistory):
    def __init__(
        self,
        flow_id: str,
        session_id: str,
    ) -> None:
        self.flow_id = flow_id
        self.session_id = session_id

    @property
    def messages(self) -> list[BaseMessage]:
        messages = get_messages(
            session_id=self.session_id,
        )
        return [m.to_lc_message() for m in messages if not m.error]  # Exclude error messages

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        for lc_message in messages:
            message = Message.from_lc_message(lc_message)
            message.session_id = self.session_id
            store_message(message, flow_id=self.flow_id)

    def clear(self) -> None:
        delete_messages(self.session_id)
