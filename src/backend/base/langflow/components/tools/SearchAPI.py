from typing import Union

from langchain_community.utilities.searchapi import SearchApiAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, MultilineInput, DictInput, MessageTextInput
from langflow.schema import Data
from langflow.field_typing import Tool


class SearchAPIComponent(LCToolComponent):
    display_name: str = "Search API"
    description: str = "Call the searchapi.io API"
    name = "SearchAPI"
    documentation: str = "https://www.searchapi.io/docs/google"

    inputs = [
        MessageTextInput(name="engine", display_name="Engine", value="google"),
        SecretStrInput(name="api_key", display_name="SearchAPI API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        DictInput(name="search_params", display_name="Search parameters", advanced=True, is_list=True),
    ]

    def run_model(self) -> Union[Data, list[Data]]:
        wrapper = self._build_wrapper()
        results = wrapper.results(query=self.input_value, **(self.search_params or {}))
        list_results = results.get("organic_results", [])
        data = [Data(data=result, text=result["snippet"]) for result in list_results]
        self.status = data
        return data

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return Tool(
            name="search_api",
            description="Search for recent results.",
            func=lambda x: wrapper.run(query=x, **(self.search_params or {})),
        )

    def _build_wrapper(self):
        return SearchApiAPIWrapper(engine=self.engine, searchapi_api_key=self.api_key)
