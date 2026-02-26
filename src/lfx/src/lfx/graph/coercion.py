"""Auto-coercion utilities for converting between Data, Message, and DataFrame types.

This module provides utilities for automatic type coercion between Langflow's
three primary data types: Data, Message, and DataFrame. The coercion is enabled
via settings and uses the same conversion logic as the Type Convert component.

IMPORTANT: Auto-coercion ONLY applies to these three types:
- Data
- Message
- DataFrame

All other types (LanguageModel, Tool, Embeddings, Retriever, Memory, etc.)
remain strictly typed with no coercion, regardless of the setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lfx.schema import Data, DataFrame, Message

# Types that can be coerced to each other
COERCIBLE_TYPES = frozenset({"Data", "Message", "DataFrame"})


@dataclass
class CoercionSettings:
    """Settings for auto-coercion behavior.

    Attributes:
        enabled: Whether auto-coercion is enabled
        auto_parse: Whether to automatically parse JSON/CSV strings during conversion
    """

    enabled: bool = False
    auto_parse: bool = False


def is_coercible_type(type_name: str) -> bool:
    """Check if a type name is a coercible type.

    Args:
        type_name: The type name to check

    Returns:
        True if the type is coercible (Data, Message, or DataFrame)
    """
    return type_name in COERCIBLE_TYPES


def are_types_coercible(source_types: list[str], target_types: list[str]) -> bool:
    """Check if source and target types can be coerced.

    Args:
        source_types: List of source output types
        target_types: List of target input types

    Returns:
        True if both have at least one coercible type
    """
    source_coercible = any(t in COERCIBLE_TYPES for t in source_types)
    target_coercible = any(t in COERCIBLE_TYPES for t in target_types)
    return source_coercible and target_coercible


def convert_to_message(value: Any) -> Message:
    """Convert input to Message type.

    Uses the same logic as the Type Convert component.

    Args:
        value: Input to convert (Message, Data, DataFrame, or dict)

    Returns:
        Message: Converted Message object
    """
    from lfx.schema import Message

    if isinstance(value, Message):
        return value

    # For Data and DataFrame, use their to_message() method
    if hasattr(value, "to_message"):
        return value.to_message()

    # For dicts, create a Message from text if present
    if isinstance(value, dict):
        text = value.get("text", str(value))
        return Message(text=text)

    # Fallback: convert to string
    return Message(text=str(value))


def convert_to_data(value: Any, *, auto_parse: bool = False) -> Data:
    """Convert input to Data type.

    Uses the same logic as the Type Convert component.

    Args:
        value: Input to convert (Message, Data, DataFrame, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        Data: Converted Data object
    """
    from lfx.components.processing.converter import parse_structured_data
    from lfx.schema import Data, DataFrame, Message

    if isinstance(value, Data) and not isinstance(value, (Message, DataFrame)):
        return value

    if isinstance(value, dict):
        return Data(value)

    if isinstance(value, Message):
        data = Data(data={"text": value.data.get("text", "")})
        return parse_structured_data(data) if auto_parse else data

    if isinstance(value, DataFrame):
        return value.to_data()

    # For other types with to_data method
    if hasattr(value, "to_data"):
        return value.to_data()

    # Fallback
    return Data(data={"value": value})


def convert_to_dataframe(value: Any, *, auto_parse: bool = False) -> DataFrame:
    """Convert input to DataFrame type.

    Uses the same logic as the Type Convert component.

    Args:
        value: Input to convert (Message, Data, DataFrame, or dict)
        auto_parse: Enable automatic parsing of structured data (JSON/CSV)

    Returns:
        DataFrame: Converted DataFrame object
    """
    import pandas as pd

    from lfx.components.processing.converter import parse_structured_data
    from lfx.schema import Data, DataFrame, Message

    if isinstance(value, DataFrame):
        return value

    if isinstance(value, dict):
        return DataFrame([value])

    # Handle pandas DataFrame
    if isinstance(value, pd.DataFrame):
        return DataFrame(data=value)

    if isinstance(value, Message):
        data = Data(data={"text": value.data.get("text", "")})
        if auto_parse:
            return parse_structured_data(data).to_dataframe()
        return data.to_dataframe()

    if isinstance(value, Data):
        return value.to_dataframe()

    # For other types with to_dataframe method
    if hasattr(value, "to_dataframe"):
        return value.to_dataframe()

    # Fallback
    return DataFrame([{"value": value}])


def auto_coerce_value(value: Any, expected_type: str, settings: CoercionSettings) -> Any:
    """Auto-convert between Data, Message, DataFrame when types differ.

    Uses the same conversion logic as the Type Convert component.
    Only coerces if:
    1. Settings are enabled
    2. Expected type is a coercible type
    3. Actual value type is also a coercible type

    Args:
        value: The value to potentially coerce
        expected_type: The expected type name (e.g., "Message", "Data", "DataFrame")
        settings: The coercion settings

    Returns:
        The coerced value if coercion applies, otherwise the original value
    """
    if not settings.enabled:
        return value

    if expected_type not in COERCIBLE_TYPES:
        return value

    # Get actual type name
    actual_type = type(value).__name__
    if actual_type == expected_type:
        return value

    if actual_type not in COERCIBLE_TYPES:
        return value

    # Apply conversion based on expected type
    if expected_type == "Message":
        return convert_to_message(value)
    if expected_type == "Data":
        return convert_to_data(value, auto_parse=settings.auto_parse)
    if expected_type == "DataFrame":
        return convert_to_dataframe(value, auto_parse=settings.auto_parse)

    return value


def auto_coerce_list(values: list, expected_type: str, settings: CoercionSettings) -> list:
    """Coerce a list of values to the expected type.

    Args:
        values: List of values to coerce
        expected_type: The expected type for each value
        settings: The coercion settings

    Returns:
        List of coerced values
    """
    return [auto_coerce_value(v, expected_type, settings) for v in values]
