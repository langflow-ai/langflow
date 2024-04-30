# from langflow.field_typing import Data
from langflow.schema import Record
from langflow.interface.custom.custom_component import CustomComponent


class StringListInput(CustomComponent):
    display_name = "String List Input"

    def build_config(self):
        return {"param": {"display_name": "String List Input", "field_type": "str", "list": True}}

    def build(self, param: list) -> Record:
        return Record(data=param)
