from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextOutput(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Interaction Panel."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Value",
                "input_types": ["Record"],
                "info": "Text or Record to be passed as output.",
            },
            "record_template": {"display_name": "Record Template", "multiline": True},
        }

    def build(self, input_value: Optional[Text] = "", record_template: str = "{text}") -> Text:
        return super().build(input_value=input_value, record_template=record_template)
