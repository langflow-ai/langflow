from langflow.base.io.text import TextComponent
from langflow.field_typing.constants import Data


class KeyPairInput(TextComponent):
    display_name = "Dictionary Output"  
    description = "Dictionary Output."

    def build_config(self):
        return {
            "input_value": {"display_name":"Dictionary","field_type":"dict"},
        }

    def build(self, input_value: dict) -> dict:
        return input_value
