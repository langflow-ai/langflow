from langflow.base.io.text import TextComponent
from langflow.field_typing.constants import Data, NestedDict

class JsonOutput(TextComponent):
    display_name = "JSON Output"  
    description = "JSON Output."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "JSON",
                "field_type": "NestedDict"
            }
        }

    def build(self, input_value: NestedDict) -> NestedDict:
        return input_value
