from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextInput(TextComponent):
    display_name = "Text Input"
    description = "Capture Text or Record and send text inputs."

    def build(
        self,
        input_value: Optional[str] = "",
        record_template: Optional[str] = "{text}",
    ) -> Text:
        return super().build(input_value=input_value, record_template=record_template)
