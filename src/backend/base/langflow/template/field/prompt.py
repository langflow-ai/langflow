from typing import Optional

from langflow.template.field.base import Input

DEFAULT_PROMPT_INTUT_TYPES = ["Message", "Text"]


class DefaultPromptField(Input):
    name: str
    display_name: Optional[str] = None
    field_type: str = "str"

    advanced: bool = False
    multiline: bool = True
    input_types: list[str] = DEFAULT_PROMPT_INTUT_TYPES
    value: str = ""  # Set the value to empty string
