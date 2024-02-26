from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text


class TextOutput(CustomComponent):
    display_name = "Text Output"
    description = "Used to pass text output to the next component."

    field_config = {
        "value": {"display_name": "Value"},
    }

    def build(self, value: Optional[str] = "") -> Text:
        self.status = value
        if not value:
            value = ""
        return value
