from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextOutput(TextComponent):
    display_name = "Text Output"
    description = "Used to pass text output to the next component."

    field_config = {
        "input_value": {"display_name": "Value"},
    }

    def build(self, input_value: Optional[Text] = "") -> Text:
        return super().build(input_value=input_value)
