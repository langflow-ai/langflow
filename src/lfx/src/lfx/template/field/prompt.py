# This file provides backwards compatibility for prompt field constants
from lfx.template.field.base import Input

# Default input types for prompt fields
DEFAULT_PROMPT_INTUT_TYPES = ["Message"]


class DefaultPromptField(Input):
    """Default prompt field for backwards compatibility."""

    field_type: str = "str"
    advanced: bool = False
    multiline: bool = True
    input_types: list[str] = DEFAULT_PROMPT_INTUT_TYPES
    value: str = ""  # Set the value to empty string
