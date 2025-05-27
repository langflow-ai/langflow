from typing import cast

from langchain_community.tools.bing_search import BingSearchResults
from langchain_community.utilities import BingSearchAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.helpers.data import data_to_dataframe
from langflow.inputs import IntInput, MessageTextInput, MultilineInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, DataFrame


class BingSearchAPIComponent(LCToolComponent):
    display_name = "Bing Search API"
    description = "Call the Bing Search API."
    name = "BingSearchAPI"
    icon = "Bing"

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
        Output(display_name="DataFrame", name="dataframe", method="fetch_content_dataframe"),
        Output(display_name="Tool", name="tool", method="build_tool"),
    ]

    def run_model(self) -> DataFrame:
        return self.fetch_content_dataframe()

    def fetch_content(self) -> list[Data]:
        if self.bing_search_url:
            wrapper = BingSearchAPIWrapper(
                bing_search_url=self.bing_search_url, bing_subscription_key=self.bing_subscription_key
            )
        else:
            wrapper = BingSearchAPIWrapper(bing_subscription_key=self.bing_subscription_key)
        results = wrapper.results(query=self.input_value, num_results=self.k)
        data = [Data(data=result, text=result["snippet"]) for result in results]
        self.status = data
        return data

    def fetch_content_dataframe(self) -> DataFrame:
        data = self.fetch_content()
        return data_to_dataframe(data)

    def build_tool(self) -> Tool:
        if self.bing_search_url:
            wrapper = BingSearchAPIWrapper(
                bing_search_url=self.bing_search_url, bing_subscription_key=self.bing_subscription_key
            )
        else:
            wrapper = BingSearchAPIWrapper(bing_subscription_key=self.bing_subscription_key)
        return cast("Tool", BingSearchResults(api_wrapper=wrapper, num_results=self.k))
