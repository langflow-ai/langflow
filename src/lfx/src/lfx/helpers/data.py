import re
from typing import Any

import orjson
from fastapi.encoders import jsonable_encoder

from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


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
