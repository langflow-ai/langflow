from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextOutput(TextComponent):
    display_name = "Text Output"
    description = "Used to send a text output."

    def build(self, input_value: Optional[Text] = "", record_template: str = "{text}") -> Text:
        return super().build(input_value=input_value, record_template=record_template)
