from typing import List

from langchain_community.tools.bing_search import BingSearchResults
from langchain_community.utilities import BingSearchAPIWrapper
from langflow.custom import Component
from langflow.inputs import MessageTextInput, SecretStrInput, IntInput, MultilineInput
from langflow.schema import Data
from langflow.template import Output


class BingSearchAPIWrapperComponent(Component):
    display_name = "BingSearchAPIWrapper"
    description = "Wrapper for Bing Search API."
    name = "BingSearchAPIWrapper"

    inputs = [
        SecretStrInput(name="bing_subscription_key", display_name="Bing Subscription Key"),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        MessageTextInput(name="bing_search_url", display_name="Bing Search URL", advanced=True),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
    ]

    outputs = [
        Output(name="api_run_model", display_name="Data", method="run_model"),
        Output(name="api_build_tool", display_name="Tool", method="build_tool"),
    ]

    def run_model(self) -> List[Data]:
        if self.bing_search_url:
            wrapper = BingSearchAPIWrapper(bing_search_url=self.bing_search_url, bing_subscription_key=self.bing_subscription_key)
        else:
            wrapper = BingSearchAPIWrapper(bing_subscription_key=self.bing_subscription_key)
        results = wrapper.results(query=self.input_value, num_results=self.k)
        data = [Data(data=result, text=result["snippet"]) for result in results]
        self.status = data
        return data

    def build_tool(self) -> BingSearchResults:
        if self.bing_search_url:
            wrapper = BingSearchAPIWrapper(bing_search_url=self.bing_search_url, bing_subscription_key=self.bing_subscription_key)
        else:
            wrapper = BingSearchAPIWrapper(bing_subscription_key=self.bing_subscription_key)
        return BingSearchResults(api_wrapper=wrapper, num_results=self.k)
