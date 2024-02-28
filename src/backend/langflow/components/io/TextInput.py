from typing import Optional

from langflow import CustomComponent
from langflow.field_typing import Text


class TextInput(CustomComponent):
    display_name = "Text Input"
    description = "Used to pass text input to the next component."

    field_config = {
        "input_value": {"display_name": "Value", "multiline": True},
    }

    def build(self, input_value: Optional[str] = "") -> Text:
        self.status = input_value
        if not input_value:
            input_value = ""
        return input_value
