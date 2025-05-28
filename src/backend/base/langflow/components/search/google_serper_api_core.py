from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper

from langflow.custom import Component
from langflow.io import IntInput, MultilineInput, Output, SecretStrInput
from langflow.schema import DataFrame
from langflow.schema.message import Message


class GoogleSerperAPICore(Component):
    display_name = "Google Serper API"
    description = "Call the Serper.dev Google Search API."
    icon = "Serper"

    inputs = [
        SecretStrInput(
            name="serper_api_key",
            display_name="Serper API Key",
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        IntInput(
            name="k",
            display_name="Number of results",
            value=4,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_serper",
        ),
    ]

    def search_serper(self) -> DataFrame:
        try:
            wrapper = self._build_wrapper()
            results = wrapper.results(query=self.input_value)
            list_results = results.get("organic", [])

            # Convert results to DataFrame using list comprehension
            df_data = [
                {
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                }
                for result in list_results
            ]

            return DataFrame(df_data)
        except (ValueError, KeyError, ConnectionError) as e:
            error_message = f"Error occurred while searching: {e!s}"
            self.status = error_message
            # Return DataFrame with error as a list of dictionaries
            return DataFrame([{"error": error_message}])

    def text_search_serper(self) -> Message:
        search_results = self.search_serper()
        text_result = search_results.to_string(index=False) if not search_results.empty else "No results found."
        return Message(text=text_result)

    def _build_wrapper(self):
        return GoogleSerperAPIWrapper(serper_api_key=self.serper_api_key, k=self.k)

    def build(self):
        return self.search_serper
