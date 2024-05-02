from langflow.interface.custom.custom_component import CustomComponent
from langflow.field_typing import Text


class CombineTextsUnsortedComponent(CustomComponent):
    display_name = "Combine Texts (Unsorted)"
    description = "Concatenate text sources into a single text chunk using a specified delimiter."
    icon = "merge"

    def build_config(self):
        return {
            "texts": {
                "display_name": "Texts",
                "info": "The first text input to concatenate.",
            },
            "delimiter": {
                "display_name": "Delimiter",
                "info": "A string used to separate the two text inputs. Defaults to a whitespace.",
            },
        }

    def build(self, texts: list[str], delimiter: str = " ") -> Text:
        combined = delimiter.join(texts)
        self.status = combined
        return combined
