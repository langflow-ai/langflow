from langchain_community.tools import DuckDuckGoSearchResults

from langflow.custom import Component
from langflow.io import IntInput, MultilineInput, Output
from langflow.schema import DataFrame


class DuckDuckGoSearchCoreComponent(Component):
    display_name: str = "DuckDuckGo Search"
    description: str = "Perform web searches using the DuckDuckGo search engine with result limiting"
    documentation: str = "https://python.langchain.com/docs/integrations/tools/ddg"
    icon: str = "DuckDuckGo"

    inputs = [
        MultilineInput(
            name="input_value",
            display_name="Search Query",
            tool_mode=True,
            required=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=4,
        ),
        IntInput(name="max_snippet_length", display_name="Max Snippet Length", value=500, advanced=True),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_duckduckgo",
        )
    ]

    def search_duckduckgo(self) -> DataFrame:
        try:
            # Initialize the DuckDuckGo search with list output format
            search = DuckDuckGoSearchResults(output_format="list")

            # Perform the search
            full_results = search.invoke(self.input_value)

            # Limit results and prepare DataFrame data
            df_data = [
                {"text": result["snippet"][: self.max_snippet_length]} for result in full_results[: self.max_results]
            ]

            # Create and return DataFrame
            return DataFrame(df_data)

        except (ValueError, AttributeError, RuntimeError) as e:
            error_message = f"Error in DuckDuckGo Search: {e!s}"
            self.status = error_message
            return DataFrame([{"text": error_message}])

    def build(self):
        return self.search_duckduckgo
