from typing import Dict, Optional

from langchain_community.utilities.searx_search import SearxSearchWrapper

from langflow.custom import CustomComponent


class SearxSearchWrapperComponent(CustomComponent):
    display_name = "SearxSearchWrapper"
    description = "Wrapper for Searx API."
    name = "SearxSearchWrapper"

    def build_config(self):
        return {
            "headers": {
                "field_type": "dict",
                "display_name": "Headers",
                "multiline": True,
                "value": '{"Authorization": "Bearer <token>"}',
            },
            "k": {"display_name": "k", "advanced": True, "field_type": "int", "value": 10},
            "searx_host": {
                "display_name": "Searx Host",
                "field_type": "str",
                "value": "https://searx.example.com",
                "advanced": True,
            },
        }

    def build(
        self,
        k: int = 10,
        headers: Optional[Dict[str, str]] = None,
        searx_host: str = "https://searx.example.com",
    ) -> SearxSearchWrapper:
        return SearxSearchWrapper(headers=headers, k=k, searx_host=searx_host)
