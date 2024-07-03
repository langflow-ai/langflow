from langchain_community.tools.searchapi import SearchAPIRun
from langchain_community.utilities.searchapi import SearchApiAPIWrapper

from langflow.custom import CustomComponent
from langflow.field_typing import Tool


class SearchApiToolComponent(CustomComponent):
    display_name: str = "SearchApi Tool"
    description: str = "Real-time search engine results API."
    name = "SearchAPITool"
    documentation: str = "https://www.searchapi.io/docs/google"
    field_config = {
        "engine": {
            "display_name": "Engine",
            "field_type": "str",
            "info": "The search engine to use.",
        },
        "api_key": {
            "display_name": "API Key",
            "field_type": "str",
            "required": True,
            "password": True,
            "info": "The API key to use SearchApi.",
        },
    }

    def build(
        self,
        engine: str,
        api_key: str,
    ) -> Tool:
        search_api_wrapper = SearchApiAPIWrapper(engine=engine, searchapi_api_key=api_key)

        tool = SearchAPIRun(api_wrapper=search_api_wrapper)

        self.status = tool
        return tool  # type: ignore
