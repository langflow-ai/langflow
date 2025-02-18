import requests
from langchain_community.utilities.serpapi import SerpAPIWrapper

from langflow.custom import Component
from langflow.inputs import DictInput, IntInput, MultilineInput, SecretStrInput
from langflow.io import Output
from langflow.schema import DataFrame


class SerpComponent(Component):
    """Component for performing searches using the SerpAPI service.

    This component allows users to search the web using SerpAPI and returns results
    in a DataFrame format. It supports customization of search parameters and result limits.
    """

    display_name = "Serp Search API"
    description = "Call Serp Search API and return results as a DataFrame"
    name = "Serp"
    icon = "SerpSearch"

    inputs = [
        SecretStrInput(
            name="serpapi_api_key",
            display_name="SerpAPI API Key",
            required=True,
        ),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        DictInput(
            name="search_params",
            display_name="Parameters",
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
            method="search_serp",
        ),
    ]

    def search_serp(self) -> DataFrame:
        """Search using SerpAPI and return results as a DataFrame."""
        if not self.serpapi_api_key:
            return DataFrame([{"error": "Invalid SerpAPI Key"}])

        try:
            # Prepare wrapper with parameters
            params = self.search_params or {}
            wrapper = SerpAPIWrapper(
                serpapi_api_key=self.serpapi_api_key,
                params={"engine": "google", "google_domain": "google.com", "gl": "us", "hl": "en", **params},
            )

            # Perform search
            full_results = wrapper.results(self.input_value)
            organic_results = full_results.get("organic_results", [])[: self.max_results]

            # Prepare results
            results = [
                {
                    "title": result.get("title", "")[: self.max_snippet_length],
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", "")[: self.max_snippet_length],
                }
                for result in organic_results
            ]

            return DataFrame(results)

        except (ValueError, KeyError) as e:
            error_message = f"Error parsing SerpAPI response: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except requests.RequestException as e:
            error_message = f"Error making request to SerpAPI: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
