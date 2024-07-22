from langchain_community.utilities.serpapi import SerpAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, DictInput, MultilineInput
from langflow.schema import Data
from langflow.field_typing import Tool


class SerpAPIComponent(LCToolComponent):
    display_name = "Serp Search API"
    description = "Call Serp Search API"
    name = "SerpAPI"

    inputs = [
        SecretStrInput(name="serpapi_api_key", display_name="SerpAPI API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        DictInput(name="search_params", display_name="Parameters", advanced=True, is_list=True),
    ]

    def run_model(self) -> list[Data]:
        wrapper = self._build_wrapper()
        results = wrapper.results(self.input_value)
        list_results = results.get("organic_results", [])
        data = [Data(data=result, text=result["snippet"]) for result in list_results]
        self.status = data
        return data

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return Tool(name="search_api", description="Search for recent results.", func=wrapper.run)

    def _build_wrapper(self) -> SerpAPIWrapper:
        if self.search_params:
            return SerpAPIWrapper(  # type: ignore
                serpapi_api_key=self.serpapi_api_key,
                params=self.search_params,
            )
        return SerpAPIWrapper(  # type: ignore
            serpapi_api_key=self.serpapi_api_key
        )
