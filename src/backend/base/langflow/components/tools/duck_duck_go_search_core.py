from langchain_community.tools import DuckDuckGoSearchRun

from langflow.custom import Component
from langflow.io import MultilineInput, IntInput, Output
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
            name="max_snippet_length", 
            display_name="Max Snippet Length", 
            value=500, 
            advanced=True
        )
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
            # Initialize the DuckDuckGo search wrapper
            wrapper = DuckDuckGoSearchRun()

            # Perform the search
            full_results = wrapper.run(f"{self.input_value} (site:*)")
            
            # Prepare DataFrame data
            df_data = [
                result[:self.max_snippet_length]  # Use max_snippet_length from input
                for result in full_results.split("\n")
            ]

            # Create and return DataFrame
            return DataFrame({"text": df_data})

        except Exception as e:
            error_message = f"Error in DuckDuckGo Search: {e!s}"
            self.status = error_message
            return DataFrame([{"text": error_message}])

    def build(self):
        return self.search_duckduckgo