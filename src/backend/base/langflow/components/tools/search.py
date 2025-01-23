import requests
from langchain_community.utilities.searchapi import SearchApiAPIWrapper

from langflow.custom import Component
from langflow.inputs import DictInput, DropdownInput, IntInput, MultilineInput, SecretStrInput
from langflow.io import Output
from langflow.schema import DataFrame


class SearchComponent(Component):
    """Component for performing searches using the SearchAPI service.

    This component allows users to search the web using SearchAPI and returns results
    in a DataFrame format. It supports customization of search parameters and result limits.
    """

    display_name = "Search API"
    description = "Call the searchapi.io API with result limiting"
    documentation = "https://www.searchapi.io/docs/google"
    icon = "SearchAPI"

    inputs = [
        DropdownInput(
            name="engine",
            display_name="Engine",
            value="google",
            options=["google", "bing", "duckduckgo"]
        ),
        SecretStrInput(
            name="api_key",
            display_name="SearchAPI API Key",
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
            required=True,
        ),
        DictInput(
            name="search_params",
            display_name="Search parameters",
            advanced=True,
            is_list=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=5,
            advanced=True,
        ),
        IntInput(
            name="max_snippet_length",
            display_name="Max Snippet Length",
            value=100,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_api",
        ),
    ]

    def search_api(self) -> DataFrame:
        """Search using SearchAPI and return results as a DataFrame."""
        if not self.api_key:
            return DataFrame([{"error": "Invalid SearchAPI Key"}])

        try:
            # Prepare wrapper with parameters
            wrapper = SearchApiAPIWrapper(
                engine=self.engine,
                searchapi_api_key=self.api_key
            )

            # Prepare search parameters
            params = self.search_params or {}

            # Perform search
            full_results = wrapper.results(query=self.input_value, **params)
            organic_results = full_results.get("organic_results", [])[:self.max_results]

            # Prepare results
            results = [
                {
                    "title": result.get("title", "")[:self.max_snippet_length],
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", "")[:self.max_snippet_length],
                }
                for result in organic_results
            ]

            return DataFrame(results)

        except (ValueError, KeyError) as e:
            error_message = f"Error parsing SearchAPI response: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except requests.RequestException as e:
            error_message = f"Error making request to SearchAPI: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
