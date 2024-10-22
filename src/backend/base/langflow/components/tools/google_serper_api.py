from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import IntInput, MultilineInput, SecretStrInput
from langflow.schema import Data


class GoogleSerperAPIComponent(LCToolComponent):
    display_name = "Google Serper API"
    description = "Call the Serper.dev Google Search API."
    name = "GoogleSerperAPI"

    inputs = [
        SecretStrInput(name="serper_api_key", display_name="Serper API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
    ]

    def run_model(self) -> Data | list[Data]:
        wrapper = self._build_wrapper()
        results = wrapper.results(query=self.input_value)
        list_results = results.get("organic", [])
        data = [Data(data=result, text=result["snippet"]) for result in list_results]
        self.status = data
        return data

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper()
        return Tool(
            name="google_search",
            description="Search Google for recent results.",
            func=wrapper.run,
        )

    def _build_wrapper(self):
        return GoogleSerperAPIWrapper(serper_api_key=self.serper_api_key, k=self.k)
