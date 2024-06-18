from typing import Union

from langchain_core.documents import Document

from langflow.schema import Data
from langflow.schema.message import Message


def docs_to_data(documents: list[Document]) -> list[Data]:
    """
    Converts a list of Documents to a list of Data.

    Args:
        documents (list[Document]): The list of Documents to convert.

    Returns:
        list[Data]: The converted list of Data.
    """
    return [Data.from_document(document) for document in documents]


def data_to_text(template: str, data: Union[Data, list[Data]], sep: str = "\n") -> str:
    """
    Converts a list of Data to a list of texts.

    Args:
        data (list[Data]): The list of Data to convert.

    Returns:
        list[str]: The converted list of texts.
    """
    if isinstance(data, (Data)):
        data = [data]
    # Check if there are any format strings in the template
    _data = []
    for value in data:
        # If it is not a record, create one with the key "text"
        if not isinstance(value, Data):
            value = Data(text=value)
        _data.append(value)

    formated_data = [template.format(data=value.data, **value.data) for value in _data]
    return sep.join(formated_data)


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
