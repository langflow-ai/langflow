from langflow import CustomComponent
from typing import Optional, Dict

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
        }

    def build(
        self,
        headers: Optional[Dict[str, str]] = None,
    ):
        if headers is None:
            headers = {"Authorization": "Bearer <token>"}
        # Placeholder for actual SearxSearchWrapper instantiation
        # Since the actual SearxSearchWrapper class is not available, 
        # it is assumed that it would be instantiated here with headers as an argument.
        pass