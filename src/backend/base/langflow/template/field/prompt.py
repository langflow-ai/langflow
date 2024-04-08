from typing import Optional

from langflow.template.field.base import TemplateField


class DefaultPromptField(TemplateField):
    name: str
    display_name: Optional[str] = None
    field_type: str = "str"

    advanced: bool = False
    multiline: bool = False  # Settings to False to allow Global Variables to be used in the prompt (temporary)
    input_types: list[str] = ["Document", "BaseOutputParser", "Record", "Text"]
    value: str = ""  # Set the value to empty string
