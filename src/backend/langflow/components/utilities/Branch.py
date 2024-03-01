from langflow import CustomComponent
from langflow.field_typing import Text


class BranchComponent(CustomComponent):
    display_name: str = "Branch Component"
    documentation: str = "http://docs.langflow.org/components/custom"
    is_conditional = True

    def build_config(self):
        return {"param": {"display_name": "Parameter"}}

    def build(self, param: Text) -> Text:
        return {"path": True, "result": param}
