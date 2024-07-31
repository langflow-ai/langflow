import warnings
from typing import List, Sequence
from uuid import UUID

from loguru import logger
from sqlalchemy import delete
from sqlmodel import Session, col, select

from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageRead, MessageTable
from langflow.services.deps import session_scope
from langflow.field_typing import BaseChatMessageHistory
from langchain_core.messages import BaseMessage

import agentops
from dotenv import load_dotenv
import os

# Load environment variables and initialize AgentOps
load_dotenv()
agentops.init(os.getenv("AGENTOPS_API_KEY"))


@agentops.record_function("get_messages")
def get_messages(
    sender: str | None = None,
    sender_name: str | None = None,
    session_id: str | None = None,
    order_by: str | None = "timestamp",
    order: str | None = "DESC",
    flow_id: UUID | None = None,
    limit: int | None = None,
) -> List[Message]:
    """
    Retrieves messages from the monitor service based on the provided filters.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        limit (Optional[int]): The maximum number of messages to retrieve.

    Returns:
        List[Data]: A list of Data objects representing the retrieved messages.
    """
    messages_read: list[Message] = []
    with session_scope() as session:
        stmt = select(MessageTable)
        if sender:
            stmt = stmt.where(MessageTable.sender == sender)
        if sender_name:
            stmt = stmt.where(MessageTable.sender_name == sender_name)
        if session_id:
            stmt = stmt.where(MessageTable.session_id == session_id)
        if flow_id:
            stmt = stmt.where(MessageTable.flow_id == flow_id)
        if order_by:
            if order == "DESC":
                col = getattr(MessageTable, order_by).desc()
            else:
                col = getattr(MessageTable, order_by).asc()
            stmt = stmt.order_by(col)
        if limit:
            stmt = stmt.limit(limit)
        messages = session.exec(stmt)
        messages_read = [Message(**d.model_dump()) for d in messages]

    agentops.record_event(
        "messages_retrieved",
        {
            "count": len(messages_read),
            "sender": sender,
            "sender_name": sender_name,
            "session_id": session_id,
            "flow_id": str(flow_id) if flow_id else None,
        },
    )
    return messages_read


@agentops.record_function("add_messages")
def add_messages(messages: Message | list[Message], flow_id: str | None = None):
    """
    Add a message to the monitor service.
    """
    try:
        if not isinstance(messages, list):
            messages = [messages]

        if not all(isinstance(message, Message) for message in messages):
            types = ", ".join([str(type(message)) for message in messages])
            raise ValueError(f"The messages must be instances of Message. Found: {types}")

        messages_models: list[MessageTable] = []
        for msg in messages:
            messages_models.append(MessageTable.from_message(msg, flow_id=flow_id))
        with session_scope() as session:
            messages_models = add_messagetables(messages_models, session)

        agentops.record_event(
            "messages_added",
            {
                "count": len(messages_models),
                "flow_id": flow_id,
            },
        )
        return [Message(**message.model_dump()) for message in messages_models]
    except Exception as e:
        logger.exception(e)
        agentops.record_event("add_messages_error", {"error": str(e)})
        raise e


@agentops.record_function("add_messagetables")
def add_messagetables(messages: list[MessageTable], session: Session):
    for message in messages:
        try:
            session.add(message)
            session.commit()
            session.refresh(message)
        except Exception as e:
            logger.exception(e)
            agentops.record_event("add_messagetable_error", {"error": str(e)})
            raise e
    return [MessageRead.model_validate(message, from_attributes=True) for message in messages]


@agentops.record_function("delete_messages")
def delete_messages(session_id: str):
    """
    Delete messages from the monitor service based on the provided session ID.

    Args:
        session_id (str): The session ID associated with the messages to delete.
    """
    with session_scope() as session:
        result = session.exec(
            delete(MessageTable)
            .where(col(MessageTable.session_id) == session_id)
            .execution_options(synchronize_session="fetch")
        )
        session.commit()

    agentops.record_event(
        "messages_deleted",
        {
            "session_id": session_id,
            "count": result.rowcount,
        },
    )


@agentops.record_function("store_message")
def store_message(
    message: Message,
    flow_id: str | None = None,
) -> list[Message]:
    """
    Stores a message in the memory.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str]): The flow ID associated with the message. When running from the CustomComponent you can access this using `self.graph.flow_id`.

    Returns:
        List[Message]: A list of data containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    if not message:
        warnings.warn("No message provided.")
        agentops.record_event("store_message_warning", {"warning": "No message provided"})
        return []

    if not message.session_id or not message.sender or not message.sender_name:
        error_msg = "All of session_id, sender, and sender_name must be provided."
        agentops.record_event("store_message_error", {"error": error_msg})
        raise ValueError(error_msg)

    stored_messages = add_messages([message], flow_id=flow_id)
    agentops.record_event(
        "message_stored",
        {
            "session_id": message.session_id,
            "sender": message.sender,
            "sender_name": message.sender_name,
            "flow_id": flow_id,
        },
    )
    return stored_messages


class LCBuiltinChatMemory(BaseChatMessageHistory):
    def __init__(
        self,
        flow_id: str,
        session_id: str,
    ) -> None:
        self.flow_id = flow_id
        self.session_id = session_id

    @property
    @agentops.record_function("LCBuiltinChatMemory.messages")
    def messages(self) -> List[BaseMessage]:
        messages = get_messages(
            session_id=self.session_id,
        )
        return [m.to_lc_message() for m in messages]

    @agentops.record_function("LCBuiltinChatMemory.add_messages")
    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        for lc_message in messages:
            message = Message.from_lc_message(lc_message)
            message.session_id = self.session_id
            store_message(message, flow_id=self.flow_id)

        agentops.record_event(
            "chat_messages_added",
            {
                "count": len(messages),
                "flow_id": self.flow_id,
                "session_id": self.session_id,
            },
        )

    @agentops.record_function("LCBuiltinChatMemory.clear")
    def clear(self) -> None:
        delete_messages(self.session_id)
        agentops.record_event(
            "chat_memory_cleared",
            {
                "flow_id": self.flow_id,
                "session_id": self.session_id,
            },
        )


# End the session when the program exits
import atexit


def end_session():
    agentops.end_session("Success")


atexit.register(end_session)
