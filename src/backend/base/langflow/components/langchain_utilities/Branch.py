from langflow import CustomComponent
from langflow.field_typing import Text
from langflow.schema import Decision


class BranchComponent(CustomComponent):
    display_name: str = "Branch Component"
    documentation: str = "http://docs.langflow.org/components/custom"
    conditional_paths: list[str] = ["True", "False"]

    def build_config(self):
        return {"param": {"display_name": "Parameter"}}

    def build(self, param: Text) -> Text:
        return Decision(path="True", result=param)
