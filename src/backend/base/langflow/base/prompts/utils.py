from copy import deepcopy

from langchain_core.documents import Document

from langflow.schema import Record
from langflow.schema.message import Message


def record_to_string(record: Record) -> str:
    """
    Convert a record to a string.

    Args:
        record (Record): The record to convert.

    Returns:
        str: The record as a string.
    """
    return record.get_text()


def dict_values_to_string(d: dict) -> dict:
    """
    Converts the values of a dictionary to strings.

    Args:
        d (dict): The dictionary whose values need to be converted.

    Returns:
        dict: The dictionary with values converted to strings.
    """
    # Do something similar to the above
    d_copy = deepcopy(d)
    for key, value in d_copy.items():
        # it could be a list of records or documents or strings
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, Message):
                    d_copy[key][i] = item.text
                elif isinstance(item, Record):
                    d_copy[key][i] = record_to_string(item)
                elif isinstance(item, Document):
                    d_copy[key][i] = document_to_string(item)
        elif isinstance(value, Message):
            d_copy[key] = value.text
        elif isinstance(value, Record):
            d_copy[key] = record_to_string(value)
        elif isinstance(value, Document):
            d_copy[key] = document_to_string(value)
    return d_copy


def document_to_string(document: Document) -> str:
    """
    Convert a document to a string.

    Args:
        document (Document): The document to convert.

    Returns:
        str: The document as a string.
    """
    return document.page_content
