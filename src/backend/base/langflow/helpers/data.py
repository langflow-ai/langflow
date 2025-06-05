import re
from collections import defaultdict
from typing import Any

import orjson
from fastapi.encoders import jsonable_encoder
from langchain_core.documents import Document

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


def docs_to_data(documents: list[Document]) -> list[Data]:
    """Converts a list of Documents to a list of Data.

    Args:
        documents (list[Document]): The list of Documents to convert.

    Returns:
        list[Data]: The converted list of Data.
    """
    return [Data.from_document(document) for document in documents]


def data_to_text_list(template: str, data: Data | list[Data]) -> tuple[list[str], list[Data]]:
    """Format text from Data objects using a template string.

    This function processes Data objects and formats their content using a template string.
    It handles various data structures and ensures consistent text formatting across different
    input types.

    Key Features:
    - Supports single Data object or list of Data objects
    - Handles nested dictionaries and extracts text from various locations
    - Uses safe string formatting with fallback for missing keys
    - Preserves original Data objects in output

    Args:
        template: Format string with placeholders (e.g., "Hello {text}")
                 Placeholders are replaced with values from Data objects
        data: Either a single Data object or a list of Data objects to format
              Each object can contain text, dictionaries, or nested data

    Returns:
        A tuple containing:
        - List[str]: Formatted strings based on the template
        - List[Data]: Original Data objects in the same order

    Raises:
        ValueError: If template is None
        TypeError: If template is not a string

    Examples:
        >>> result = data_to_text_list("Hello {text}", Data(text="world"))
        >>> assert result == (["Hello world"], [Data(text="world")])

        >>> result = data_to_text_list(
        ...     "{name} is {age}",
        ...     Data(data={"name": "Alice", "age": 25})
        ... )
        >>> assert result == (["Alice is 25"], [Data(data={"name": "Alice", "age": 25})])
    """
    if data is None:
        return [], []

    if template is None:
        msg = "Template must be a string, but got None."
        raise ValueError(msg)

    if not isinstance(template, str):
        msg = f"Template must be a string, but got {type(template)}"
        raise TypeError(msg)

    formatted_text: list[str] = []
    processed_data: list[Data] = []

    data_list = [data] if isinstance(data, Data) else data

    data_objects = [item if isinstance(item, Data) else Data(text=str(item)) for item in data_list]

    for data_obj in data_objects:
        format_dict = {}

        if isinstance(data_obj.data, dict):
            format_dict.update(data_obj.data)

            if isinstance(data_obj.data.get("data"), dict):
                format_dict.update(data_obj.data["data"])

            elif format_dict.get("error"):
                format_dict["text"] = format_dict["error"]

        format_dict["data"] = data_obj.data

        safe_dict = defaultdict(str, format_dict)

        try:
            formatted_text.append(template.format_map(safe_dict))
            processed_data.append(data_obj)
        except ValueError as e:
            msg = f"Error formatting template: {e!s}"
            raise ValueError(msg) from e

    return formatted_text, processed_data


def data_to_text(template: str, data: Data | list[Data], sep: str = "\n") -> str:
    r"""Converts data into a formatted text string based on a given template.

    Args:
        template (str): The template string used to format each data item.
        data (Data | list[Data]): A single data item or a list of data items to be formatted.
        sep (str, optional): The separator to use between formatted data items. Defaults to "\n".

    Returns:
        str: A string containing the formatted data items separated by the specified separator.
    """
    formatted_text, _ = data_to_text_list(template, data)
    sep = "\n" if sep is None else sep
    return sep.join(formatted_text)


def messages_to_text(template: str, messages: Message | list[Message]) -> str:
    """Converts a list of Messages to a list of texts.

    Args:
        template (str): The template to use for the conversion.
        messages (list[Message]): The list of Messages to convert.

    Returns:
        list[str]: The converted list of texts.
    """
    if isinstance(messages, (Message)):
        messages = [messages]
    # Check if there are any format strings in the template
    messages_ = []
    for message in messages:
        # If it is not a message, create one with the key "text"
        if not isinstance(message, Message):
            msg = "All elements in the list must be of type Message."
            raise TypeError(msg)
        messages_.append(message)

    formated_messages = [template.format(data=message.model_dump(), **message.model_dump()) for message in messages_]
    return "\n".join(formated_messages)


def clean_string(s):
    # Remove empty lines
    s = re.sub(r"^\s*$", "", s, flags=re.MULTILINE)
    # Replace three or more newlines with a double newline
    return re.sub(r"\n{3,}", "\n\n", s)


def _serialize_data(data: Data) -> str:
    """Serialize Data object to JSON string."""
    # Convert data.data to JSON-serializable format
    serializable_data = jsonable_encoder(data.data)
    # Serialize with orjson, enabling pretty printing with indentation
    json_bytes = orjson.dumps(serializable_data, option=orjson.OPT_INDENT_2)
    # Convert bytes to string and wrap in Markdown code blocks
    return "```json\n" + json_bytes.decode("utf-8") + "\n```"


def safe_convert(data: Any, *, clean_data: bool = False) -> str:
    """Safely convert input data to string."""
    try:
        if isinstance(data, str):
            return clean_string(data)
        if isinstance(data, Message):
            return data.get_text()
        if isinstance(data, Data):
            return clean_string(_serialize_data(data))
        if isinstance(data, DataFrame):
            if clean_data:
                # Remove empty rows
                data = data.dropna(how="all")
                # Remove empty lines in each cell
                data = data.replace(r"^\s*$", "", regex=True)
                # Replace multiple newlines with a single newline
                data = data.replace(r"\n+", "\n", regex=True)

            # Replace pipe characters to avoid markdown table issues
            processed_data = data.replace(r"\|", r"\\|", regex=True)

            return processed_data.to_markdown(index=False)

        return clean_string(str(data))
    except (ValueError, TypeError, AttributeError) as e:
        msg = f"Error converting data: {e!s}"
        raise ValueError(msg) from e


def data_to_dataframe(data: Data | list[Data]) -> DataFrame:
    """Converts a Data object or a list of Data objects to a DataFrame.

    Args:
        data (Data | list[Data]): The Data object or list of Data objects to convert.

    Returns:
        DataFrame: The converted DataFrame.
    """
    if isinstance(data, Data):
        return DataFrame([data.data])
    return DataFrame(data=[d.data for d in data])
