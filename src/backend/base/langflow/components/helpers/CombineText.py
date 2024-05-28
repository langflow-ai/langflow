from langflow.custom import CustomComponent
from langflow.field_typing import Text


class CombineTextComponent(CustomComponent):
    display_name = "Combine Text"
    description = "Concatenate two text sources into a single text chunk using a specified delimiter."
    icon = "merge"

    def build_config(self):
        return {
            "text1": {
                "display_name": "First Text",
                "info": "The first text input to concatenate.",
            },
            "text2": {
                "display_name": "Second Text",
                "info": "The second text input to concatenate.",
            },
            "delimiter": {
                "display_name": "Delimiter",
                "info": "A string used to separate the two text inputs. Defaults to a whitespace.",
            },
        }

    def build(self, text1: str, text2: str, delimiter: str = " ") -> Text:
        combined = delimiter.join([text1, text2])
        self.status = combined
        return combined
