DEFAULT_CUSTOM_COMPONENT_CODE = """from langflow import CustomComponent

from langflow.field_typing import *

class Component(CustomComponent):
    display_name: str = "Custom Component"
    description: str = "Create any custom component you want!"

    def build_config(self):
        return { "param": { "display_name": "Parameter" } }

    def build(self, param: Data) -> Data:
        return params

"""
