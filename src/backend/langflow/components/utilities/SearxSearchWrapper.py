from langflow import CustomComponent
from typing import Optional, Dict
from langchain_community.utilities.searx_search import SearxSearchWrapper
class SearxSearchWrapperComponent(CustomComponent):
    display_name = "SearxSearchWrapper"
    description = "Wrapper for Searx API."

    def build_config(self):
        return {
            "headers": {
                "field_type":"dict",
                "display_name": "Headers",
                "multiline": True,
                "value": '{"Authorization": "Bearer <token>"}'
            },
            "k": {
                "display_name": "k",
                "advanced": True,
                "field_type": "int",
                "value": 10
            },
        }

    def build(
        self,
        k: Optional[int] = 10,
        headers: Optional[Dict[str, str]] = None,
    ):
        return SearxSearchWrapper(headers=headers,k=k)
