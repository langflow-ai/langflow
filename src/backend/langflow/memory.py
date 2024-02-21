from typing import Optional, Union

from langflow.schema import Record
from langflow.services.deps import get_monitor_service
from langflow.services.monitor.schema import MessageModel
from loguru import logger


def get_messages(
    sender: Optional[str] = None,
    sender_name: Optional[str] = None,
    session_id: Optional[str] = None,
    order_by: Optional[str] = "timestamp",
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
    )

    records: list[Record] = []

    for row in messages_df.itertuples():
        record = Record(
            text=row.message,
            data={
                "sender": row.sender,
                "sender_name": row.sender_name,
                "session_id": row.session_id,
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
