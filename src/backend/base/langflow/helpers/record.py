from typing import Union

from langchain_core.documents import Document

from langflow.schema import Record
from langflow.schema.message import Message


def docs_to_records(documents: list[Document]) -> list[Record]:
    """
    Converts a list of Documents to a list of Records.

    Args:
        documents (list[Document]): The list of Documents to convert.

    Returns:
        list[Record]: The converted list of Records.
    """
    return [Record.from_document(document) for document in documents]


def records_to_text(template: str, records: Union[Record, list[Record]]) -> str:
    """
    Converts a list of Records to a list of texts.

    Args:
        records (list[Record]): The list of Records to convert.

    Returns:
        list[str]: The converted list of texts.
    """
    if isinstance(records, (Record)):
        records = [records]
    # Check if there are any format strings in the template
    _records = []
    for record in records:
        # If it is not a record, create one with the key "text"
        if not isinstance(record, Record):
            record = Record(text=record)
        _records.append(record)

    formated_records = [template.format(data=record.data, **record.data) for record in _records]
    return "\n".join(formated_records)


def messages_to_text(template: str, messages: Union[Message, list[Message]]) -> str:
    """
    Converts a list of Messages to a list of texts.

    Args:
        messages (list[Message]): The list of Messages to convert.

    Returns:
        list[str]: The converted list of texts.
    """
    if isinstance(messages, (Message)):
        messages = [messages]
    # Check if there are any format strings in the template
    _messages = []
    for message in messages:
        # If it is not a message, create one with the key "text"
        if not isinstance(message, Message):
            raise ValueError("All elements in the list must be of type Message.")
        _messages.append(message)

    formated_messages = [template.format(data=message.model_dump(), **message.model_dump()) for message in _messages]
    return "\n".join(formated_messages)
