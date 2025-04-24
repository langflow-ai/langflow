from langchain_core.documents import Document

from langflow.schema import JSON


def data_to_string(record: JSON) -> str:
    """Convert a record to a string.

    Args:
        record (Data): The record to convert.

    Returns:
        str: The record as a string.
    """
    return record.get_text()


def dict_values_to_string(d: dict) -> dict:
    """Converts the values of a dictionary to strings.

    Args:
        d (dict): The dictionary whose values need to be converted.

    Returns:
        dict: The dictionary with values converted to strings.
    """
    from langflow.schema.message import Message

    for key, value in d.items():
        # it could be a list of data or documents or strings
        if isinstance(value, list):
            for i in range(len(value)):
                item = value[i]
                if isinstance(item, Message):
                    value[i] = item.text
                elif isinstance(item, JSON):
                    value[i] = item.get_text()
                elif isinstance(item, Document):
                    value[i] = item.page_content
        elif isinstance(value, Message):
            d[key] = value.text
        elif isinstance(value, JSON):
            d[key] = value.get_text()
        elif isinstance(value, Document):
            d[key] = value.page_content
    return d


def document_to_string(document: Document) -> str:
    """Convert a document to a string.

    Args:
        document (Document): The document to convert.

    Returns:
        str: The document as a string.
    """
    return document.page_content
