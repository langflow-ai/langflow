from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextInput(TextComponent):
    display_name = "Text Input"
    description = "Used to pass text input to the next component."

    def build(self, input_value: Optional[str] = "") -> Text:
        return super().build(input_value=input_value)
