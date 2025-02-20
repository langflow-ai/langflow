from typing import Any

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import default_settings

from langflow.schema.data import Data


def convert_to_langchain_type(value):
    from langflow.schema.message import Message

    if isinstance(value, dict):
        value = {key: convert_to_langchain_type(val) for key, val in value.items()}
    elif isinstance(value, list):
        value = [convert_to_langchain_type(v) for v in value]
    elif isinstance(value, Message):
        if "prompt" in value:
            value = value.load_lc_prompt()
        elif value.sender:
            value = value.to_lc_message()
        else:
            value = value.to_lc_document()
    elif isinstance(value, Data):
        value = value.to_lc_document() if "text" in value.data else value.data
    return value


def convert_to_langchain_types(io_dict: dict[str, Any]):
    converted = {}
    for key, value in io_dict.items():
        converted[key] = convert_to_langchain_type(value)
    return converted


# Constants
MIN_SECRET_LENGTH = 8


def check_string_for_secrets(s: str | float | bool | None) -> tuple[list, str]:
    """Check a string for secrets using scan_line and return both the detections and a string with secrets replaced.

    Args:
        s: The input string to check for secrets

    Returns:
        A tuple containing:
        - list: List of detected secrets (PotentialSecret objects)
        - str: The input string with any detected secrets replaced with a standard message
    """
    if s is None:
        return [], ""

    # Convert non-string input to string
    s_str = str(s)

    # Use detect-secrets to find secrets
    with default_settings():
        detections = list(scan_line(s_str))

    # If no secrets found, return original string
    if not detections:
        return [], s_str

    # Filter out false positives
    valid_detections = []
    for detection in detections:
        if not hasattr(detection, "secret_value") or not detection.secret_value:
            continue

        secret_str = str(detection.secret_value)
        # Skip if secret is too short or just numbers
        if len(secret_str) < MIN_SECRET_LENGTH or secret_str.isdigit():
            continue

        valid_detections.append(detection)

    if not valid_detections:
        return [], s_str

    # Return the fixed string for any valid detection
    return valid_detections, "[Secret Redacted]"
