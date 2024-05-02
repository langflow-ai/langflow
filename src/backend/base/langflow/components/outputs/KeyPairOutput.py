from langflow.base.io.text import TextComponent
from langflow.field_typing.constants import Data


class KeyPairOutput(TextComponent):
    display_name = "Dictionary Output"  
    description = "Dictionary Output."

    def build_config(self):
        return {
            "input_value": {
                "display_name": "Dictionaries",
                "field_type": "dict",
                "list": True
            }
        }

    def build(self, input_value: dict) -> dict:
        return input_value
