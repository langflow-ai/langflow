from langflow.interface.custom.custom_component import CustomComponent
from langflow.field_typing import Text


class CombineTextComponent(CustomComponent):
    display_name = "Combine Text"
    description = "Concatenate multiple text sources into a single text chunk using a specified delimiter."
    icon = "merge"

    def build_config(self):
        return {
            "texts": {
                "display_name": "Texts",
                "info": "Multiple text inputs to concatenate.",
            },
            "delimiter": {
                "display_name": "Delimiter",
                "info": "A string used to separate each text input. Defaults to a whitespace.",
            },
        }

    def build(self, texts: list[str], delimiter: str = " ") -> Text:
        combined = delimiter.join(texts)
        self.status = combined
        return combined
