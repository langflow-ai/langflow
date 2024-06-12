# from langflow.field_typing import Data
from langflow.custom import CustomComponent
from langflow.schema import Data


class Component(CustomComponent):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "custom_components"

    def build_config(self):
        return {"param": {"display_name": "Parameter"}}

    def build(self, param: str) -> Data:
        return Data(data=param)
