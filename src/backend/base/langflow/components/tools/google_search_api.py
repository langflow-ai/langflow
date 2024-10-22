from langchain_core.tools import Tool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import IntInput, MultilineInput, SecretStrInput
from langflow.schema import Data


class GoogleSearchAPIComponent(LCToolComponent):
    display_name = "Google Search API"
    description = "Call Google Search API."
    name = "GoogleSearchAPI"

    inputs = [
        SecretStrInput(name="google_api_key", display_name="Google API Key", required=True),
        SecretStrInput(name="google_cse_id", display_name="Google CSE ID", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
    ]

    def run_model(self) -> Data | list[Data]:
        wrapper = self._build_wrapper()
        results = wrapper.results(query=self.input_value, num_results=self.k)
        data = [Data(data=result, text=result["snippet"]) for result in results]
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
        try:
            from langchain_google_community import GoogleSearchAPIWrapper
        except ImportError as e:
            msg = "Please install langchain-google-community to use GoogleSearchAPIWrapper."
            raise ImportError(msg) from e
        return GoogleSearchAPIWrapper(google_api_key=self.google_api_key, google_cse_id=self.google_cse_id, k=self.k)
