from langchain_core.documents import Document

from langflow.schema import Record


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
    for key, value in d.items():
        # it could be a list of records or documents or strings
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, Record):
                    d[key][i] = record_to_string(item)
                elif isinstance(item, Document):
                    d[key][i] = document_to_string(item)
        elif isinstance(value, Record):
            d[key] = record_to_string(value)
        elif isinstance(value, Document):
            d[key] = document_to_string(value)
    return d


def document_to_string(document: Document) -> str:
    """
    Convert a document to a string.

    Args:
        document (Document): The document to convert.

    Returns:
        str: The document as a string.
    """
    return document.page_content
