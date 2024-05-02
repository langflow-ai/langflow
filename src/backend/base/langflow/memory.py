import warnings
from typing import Optional, Union

from loguru import logger

from langflow.schema import Record
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

    records: list[Record] = []
    # messages_df has a timestamp
    # it gets the last 5 messages, for example
    # but now they are ordered from most recent to least recent
    # so we need to reverse the order
    messages_df = messages_df[::-1] if order == "DESC" else messages_df
    for row in messages_df.itertuples():
        record = Record(
            data={
                "text": row.message,
                "sender": row.sender,
                "sender_name": row.sender_name,
                "session_id": row.session_id,
                "timestamp": row.timestamp,
            },
        )
        records.append(record)

    return records


def add_messages(records: Union[list[Record], Record]):
    """
    Add a message to the monitor service.
    """
    try:
        monitor_service = get_monitor_service()

        if isinstance(records, Record):
            records = [records]

        if not all(isinstance(record, (Record, str)) for record in records):
            types = ", ".join([str(type(record)) for record in records])
            raise ValueError(f"The records must be instances of Record. Found: {types}")

        messages: list[MessageModel] = []
        for record in records:
            messages.append(MessageModel.from_record(record))

        for message in messages:
            try:
                monitor_service.add_message(message)
            except Exception as e:
                logger.error(f"Error adding message to monitor service: {e}")
                logger.exception(e)
                raise e
        return records
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
    monitor_service.delete_messages(session_id)


def store_message(
    message: Union[str, Record],
    session_id: Optional[str] = None,
    sender: Optional[str] = None,
    sender_name: Optional[str] = None,
) -> list[Record]:

    if not message:
        warnings.warn("No message provided.")
        return []

    if not session_id or not sender or not sender_name:
        raise ValueError("All of session_id, sender, and sender_name must be provided.")

    if isinstance(message, Record):
        record = message
        record.data.update(
            {
                "session_id": session_id,
                "sender": sender,
                "sender_name": sender_name,
            }
        )
    elif isinstance(message, str):
        record = Record(
            data={
                "text": message,
                "session_id": session_id,
                "sender": sender,
                "sender_name": sender_name,
            },
        )

    return add_messages([record])
