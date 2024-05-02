# from langflow.field_typing import Data
from langflow.schema import Record
from langflow.interface.custom.custom_component import CustomComponent


class StringListOutput(CustomComponent):
    display_name = "String List Output"

    def build_config(self):
        return {"input_value": {"display_name": "String List Output", "field_type": "str", "list": True}}

    def build(self, input_value: list) -> Record:
        return Record(data=input_value)