from typing import Optional

from langflow.base.io.text import TextComponent
from langflow.field_typing import Text


class PDFOutput(TextComponent):
    display_name = "PDF Output"
    description = "Used view pdf files"

    field_config = {
        "input_value": {"display_name": "pdf","info":"A pdf url","input_types":["Text"]},
    }

    def build(self, input_value: Text) -> Text:
        return input_value
