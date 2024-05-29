from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class TextOutput(TextComponent):
    display_name = "Text Output"
    description = "Display a text output in the Playground."
    icon = "type"

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Value",
                "input_types": ["Record", "Text"],
                "info": "Text or Record to be passed as output.",
            },
            "record_template": {
                "display_name": "Record Template",
                "multiline": True,
                "info": "Template to convert Record to Text. If left empty, it will be dynamically set to the Record's text key.",
                "advanced": True,
            },
        }

    def build(self, input_value: Optional[Text] = "", record_template: Optional[str] = "") -> Text:
        return super().build(input_value=input_value, record_template=record_template)
