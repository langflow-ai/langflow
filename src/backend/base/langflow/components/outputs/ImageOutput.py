from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text

class ImageOutput(TextComponent):
    display_name = "Image Output"
    description = "Display images"

    field_config = {
        "input_value": {"display_name": "image","info":"A image url","input_types":["Text"]},
    }

    def build(self, input_value: Text) -> Text:
        return input_value
