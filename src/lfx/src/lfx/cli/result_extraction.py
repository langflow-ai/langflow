"""Result extraction utilities for LFX CLI.

This module provides functionality to extract and format results
from executed LFX graphs in various formats (JSON, text, structured).
"""

import json
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.schema.message import Message


def _value_to_json_string(value: Any) -> str:
    """Convert a value to a JSON string representation.

    Args:
        value: The value to convert.

    Returns:
        A JSON string representation of the value.
    """
    if value is None:
        return "null"

    # Pydantic models with model_dump_json
    if hasattr(value, "model_dump_json") and callable(value.model_dump_json):
        try:
            return json.dumps(json.loads(value.model_dump_json()), ensure_ascii=False)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug("Failed to serialize via model_dump_json: %s", e)

    # Pydantic models with model_dump
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return json.dumps(value.model_dump(), ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.debug("Failed to serialize via model_dump: %s", e)

    # Data objects
    if hasattr(value, "data") and not isinstance(value, type):
        try:
            return json.dumps(value.data, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.debug("Failed to serialize data attribute: %s", e)

    # Dict/list/primitives
    if isinstance(value, dict | list | str | int | float | bool):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.debug("Failed to serialize primitive type: %s", e)

    # Fallback to string
    return str(value)


def _value_to_text_string(value: Any) -> str:
    """Convert a value to a plain text string representation.

    Args:
        value: The value to convert.

    Returns:
        A plain text string representation of the value.
    """
    if value is None:
        return ""

    # Message objects - extract text
    if hasattr(value, "text"):
        return str(value.text)

    # Data objects
    if hasattr(value, "data") and not isinstance(value, type):
        data = value.data
        if isinstance(data, dict) and "text" in data:
            return str(data["text"])
        if isinstance(data, str):
            return data
        # For non-text data, convert to JSON string
        try:
            return json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(data)

    # Dict with text key
    if isinstance(value, dict) and "text" in value:
        return str(value["text"])

    # String
    if isinstance(value, str):
        return value

    # Other types - convert to JSON or string
    if isinstance(value, dict | list):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.debug("Failed to convert dict/list to JSON: %s", e)
            return str(value)

    # Pydantic models
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return json.dumps(value.model_dump(), ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.debug("Failed to serialize Pydantic model: %s", e)
            return str(value)

    return str(value)


def _extract_value(value: Any, *, extract_text: bool = True) -> Any:
    """Extract the most appropriate representation from a value.

    Handles various output types: Message, Data, dict, list, Pydantic models, etc.

    Args:
        value: The value to extract from.
        extract_text: If True, extract text from Message/Data objects.

    Returns:
        The extracted value in its most appropriate form.
    """
    if value is None:
        return None

    # Message objects - extract text if requested
    if hasattr(value, "text") and extract_text:
        return value.text

    # Data objects - return the data dict
    if hasattr(value, "data") and not isinstance(value, type):
        data = value.data
        if isinstance(data, dict):
            # If data has a "text" key and extract_text is True, return just the text
            if extract_text and "text" in data:
                return data["text"]
            return data
        return data

    # Pydantic models - convert to dict
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump()

    # Already a dict, list, str, int, float, bool - return as-is
    if isinstance(value, dict | list | str | int | float | bool):
        return value

    # Fallback: convert to string
    return str(value)


def _get_result_type(value: Any) -> str:
    """Determine the type label for a result value.

    Args:
        value: The value to determine the type for.

    Returns:
        A string label describing the type.
    """
    if hasattr(value, "text"):
        return "message"
    if hasattr(value, "data"):
        return "data"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str):
        return "text"
    return "object"


def _extract_run_flow_result(result: Any) -> Any | None:
    """Extract result from a Run Flow component.

    Args:
        result: The result object from the Run Flow component.

    Returns:
        The extracted value or None if extraction fails.
    """
    try:
        result_dict = getattr(result, "result_dict", None)
        if result_dict and hasattr(result_dict, "results"):
            results_data = result_dict.results
            for key, value in results_data.items():
                # Skip tool outputs
                if key == "component_as_tool":
                    continue
                if value is not None:
                    return value
    except (AttributeError, TypeError, KeyError) as e:
        logger.debug("Failed to extract Run Flow result: %s", e)
    return None


def extract_message_from_result(results: list) -> str:
    """Extract the message from the results as a JSON string.

    Args:
        results: List of result objects from graph execution.

    Returns:
        A JSON string representation of the message, or "No response generated".
    """
    for result in results:
        if not (hasattr(result, "vertex") and result.vertex.custom_component):
            continue

        display_name = result.vertex.custom_component.display_name

        # Handle Chat Output component
        if display_name == "Chat Output":
            message: Message | None = result.result_dict.results.get("message")
            if message is None:
                continue
            return _value_to_json_string(message)

        # Handle Run Flow component - extract message from subflow result
        if display_name == "Run Flow":
            value = _extract_run_flow_result(result)
            if value is not None:
                return _value_to_json_string(value)

    return "No response generated"


def extract_text_from_result(results: list) -> str:
    """Extract the text content from the results.

    Args:
        results: List of result objects from graph execution.

    Returns:
        The text content, or "No response generated".
    """
    for result in results:
        if not (hasattr(result, "vertex") and result.vertex.custom_component):
            continue

        display_name = result.vertex.custom_component.display_name

        # Handle Chat Output component
        if display_name == "Chat Output":
            message: dict | Message = result.result_dict.results.get("message")
            return _value_to_text_string(message)

        # Handle Run Flow component - extract text from subflow result
        if display_name == "Run Flow":
            value = _extract_run_flow_result(result)
            if value is not None:
                return _value_to_text_string(value)

    return "No response generated"


def extract_structured_result(results: list, *, extract_text: bool = True) -> dict:
    """Extract structured result data from the results.

    Handles various output types including Message, Data, dict, list, and custom objects.

    Args:
        results: List of result objects from graph execution.
        extract_text: If True, extract text from Message/Data objects.

    Returns:
        A dictionary containing the structured result with metadata.
    """
    for result in results:
        if not (hasattr(result, "vertex") and result.vertex.custom_component):
            continue

        display_name = result.vertex.custom_component.display_name

        # Handle Chat Output component
        if display_name == "Chat Output":
            message: Message | None = result.result_dict.results.get("message")
            if message is None:
                continue
            try:
                result_message = _extract_value(message, extract_text=extract_text)
            except (AttributeError, TypeError, ValueError) as e:
                return {
                    "text": str(message),
                    "type": "message",
                    "component": display_name,
                    "component_id": result.vertex.id,
                    "success": True,
                    "warning": f"Could not extract value properly: {e}",
                }

            return {
                "result": result_message,
                "type": "message",
                "component": display_name,
                "component_id": result.vertex.id,
                "success": True,
            }

        # Handle Run Flow component - extract result from subflow execution
        if display_name == "Run Flow":
            try:
                result_dict = getattr(result, "result_dict", None)
                if result_dict and hasattr(result_dict, "results"):
                    results_data = result_dict.results
                    for key, value in results_data.items():
                        # Skip tool outputs
                        if key == "component_as_tool":
                            continue

                        extracted = _extract_value(value, extract_text=extract_text)
                        if extracted is not None:
                            return {
                                "result": extracted,
                                "type": _get_result_type(value),
                                "component": display_name,
                                "component_id": result.vertex.id,
                                "output_name": key,
                                "success": True,
                            }
            except (AttributeError, TypeError, KeyError) as e:
                logger.debug("Failed to extract structured Run Flow result: %s", e)

    return {"text": "No response generated", "type": "error", "success": False}
