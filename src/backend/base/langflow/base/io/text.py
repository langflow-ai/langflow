from typing import Optional

from langflow.field_typing import Text
from langflow.interface.custom.custom_component import CustomComponent


class TextComponent(CustomComponent):
    display_name = "Text Component"
    description = "Used to pass text to the next component."

    field_config = {
        "input_value": {"display_name": "Value", "multiline": True},
    }

    def build(self, input_value: Optional[str] = "") -> Text:
        self.status = input_value
        if not input_value:
            input_value = ""
        return input_value
