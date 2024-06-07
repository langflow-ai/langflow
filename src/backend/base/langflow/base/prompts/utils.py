import base64
from copy import deepcopy

from langchain_core.documents import Document

from langflow.schema import Record
from langflow.services.deps import get_storage_service


def record_to_string(record: Record) -> str:
    """
    Convert a record to a string.

    Args:
        record (Record): The record to convert.

    Returns:
        str: The record as a string.
    """
    return record.get_text()


async def dict_values_to_string(d: dict) -> dict:
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
                if isinstance(item, Record):
                    d_copy[key][i] = item.to_lc_message()
                elif isinstance(item, Document):
                    d_copy[key][i] = document_to_string(item)
        elif isinstance(value, Record):
            if "files" in value and value.files:
                files = await get_file_paths(value.files)
                value.files = files
            d_copy[key] = value.to_lc_message()
        elif isinstance(value, Document):
            d_copy[key] = document_to_string(value)
    return d_copy


async def get_file_paths(files: list[str]):
    storage_service = get_storage_service()
    file_paths = []
    for file in files:
        flow_id, file_name = file.split("/")
        file_paths.append(storage_service.build_full_path(flow_id=flow_id, file_name=file_name))
    return file_paths


async def get_files(
    file_paths: str,
    convert_to_base64: bool = False,
):
    storage_service = get_storage_service()
    file_objects = []
    for file_path in file_paths:
        flow_id, file_name = file_path.split("/")
        file_object = await storage_service.get_file(flow_id=flow_id, file_name=file_name)
        if convert_to_base64:
            file_object = base64.b64encode(file_object).decode("utf-8")
        file_objects.append(file_object)
    return file_objects


def document_to_string(document: Document) -> str:
    """
    Convert a document to a string.

    Args:
        document (Document): The document to convert.

    Returns:
        str: The document as a string.
    """
    return document.page_content
