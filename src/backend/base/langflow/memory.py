import warnings
from typing import List, Optional

from loguru import logger

from langflow.schema.message import Message
from langflow.services.deps import get_monitor_service
from langflow.services.monitor.schema import MessageModel


def get_messages(
    sender: Optional[str] = None,
    sender_name: Optional[str] = None,
    session_id: Optional[str] = None,
    order_by: Optional[str] = "timestamp",
    order: Optional[str] = "DESC",
    limit: Optional[int] = None,
):
    """
    Retrieves messages from the monitor service based on the provided filters.

    Args:
        sender (Optional[str]): The sender of the messages (e.g., "Machine" or "User")
        sender_name (Optional[str]): The name of the sender.
        session_id (Optional[str]): The session ID associated with the messages.
        order_by (Optional[str]): The field to order the messages by. Defaults to "timestamp".
        limit (Optional[int]): The maximum number of messages to retrieve.

    Returns:
        List[Record]: A list of Record objects representing the retrieved messages.
    """
    monitor_service = get_monitor_service()
    messages_df = monitor_service.get_messages(
        sender=sender,
        sender_name=sender_name,
        session_id=session_id,
        order_by=order_by,
        limit=limit,
        order=order,
    )

    messages: list[Message] = []
    # messages_df has a timestamp
    # it gets the last 5 messages, for example
    # but now they are ordered from most recent to least recent
    # so we need to reverse the order
    messages_df = messages_df[::-1] if order == "DESC" else messages_df
    for row in messages_df.itertuples():
        msg = Message(
            text=row.text,
            sender=row.sender,
            session_id=row.session_id,
            sender_name=row.sender_name,
            timestamp=row.timestamp,
        )

        messages.append(msg)

    return messages


def add_messages(messages: Message | list[Message], flow_id: Optional[str] = None):
    """
    Add a message to the monitor service.
    """
    try:
        monitor_service = get_monitor_service()
        if not isinstance(messages, list):
            messages = [messages]

        if not all(isinstance(message, Message) for message in messages):
            types = ", ".join([str(type(message)) for message in messages])
            raise ValueError(f"The messages must be instances of Message. Found: {types}")

        messages_models: list[MessageModel] = []
        for msg in messages:
            msg.timestamp = monitor_service.get_timestamp()
            messages_models.append(MessageModel.from_message(msg, flow_id=flow_id))

        for message_model in messages_models:
            try:
                monitor_service.add_message(message_model)
            except Exception as e:
                logger.error(f"Error adding message to monitor service: {e}")
                logger.exception(e)
                raise e
        return messages_models
    except Exception as e:
        logger.exception(e)
        raise e


def delete_messages(session_id: str):
    """
    Delete messages from the monitor service based on the provided session ID.

    Args:
        session_id (str): The session ID associated with the messages to delete.
    """
    monitor_service = get_monitor_service()
    monitor_service.delete_messages_session(session_id)


def store_message(
    message: Message,
    flow_id: Optional[str] = None,
) -> List[Message]:
    """
    Stores a message in the memory.

    Args:
        message (Message): The message to store.
        flow_id (Optional[str]): The flow ID associated with the message. When running from the CustomComponent you can access this using `self.graph.flow_id`.

    Returns:
        List[Message]: A list of records containing the stored message.

    Raises:
        ValueError: If any of the required parameters (session_id, sender, sender_name) is not provided.
    """
    if not message:
        warnings.warn("No message provided.")
        return []

    if not message.session_id or not message.sender or not message.sender_name:
        raise ValueError("All of session_id, sender, and sender_name must be provided.")

    return add_messages([message], flow_id=flow_id)
