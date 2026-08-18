from urllib.parse import urlencode

import httpx
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.template.field.base import Output

SEARCH_ENDPOINT = "https://api.serply.io/v1/search/"
MIN_RESULTS = 1
MAX_RESULTS = 100


class SerplySearchComponent(Component):
    """Component for performing web searches using the Serply SERP API."""

    display_name = "Serply Search"
    description = "Search Google results as JSON using the Serply API."
    documentation = "https://serply.io/docs"
    icon = "search"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Search Query",
            required=True,
            info="The search query to execute with Serply.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="serply_api_key",
            display_name="Serply API Key",
            required=True,
            info="Your Serply API key. Get one at https://serply.io.",
            password=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            value=10,
            required=False,
            advanced=True,
            info="Maximum number of organic results to return (1-100).",
        ),
    ]

    outputs = [
        Output(display_name="Table", name="dataframe", method="fetch_content_dataframe"),
    ]

    def _search(self) -> dict:
        """Call the Serply search endpoint and return the decoded JSON payload."""
        if not self.serply_api_key:
            msg = "Serply API key is required. Set the Serply API Key input."
            raise ValueError(msg)

        num = max(MIN_RESULTS, min(int(self.max_results or 10), MAX_RESULTS))
        query = urlencode({"q": self.input_value or "", "num": num})
        headers = {
            "X-Api-Key": self.serply_api_key,
            "Accept": "application/json",
            # Serply sits behind Cloudflare, which blocks the default httpx
            # User-Agent with a 1010 error, so send an explicit one.
            "User-Agent": "langflow-serply-bundle",
        }
        response = httpx.get(f"{SEARCH_ENDPOINT}{query}", headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_content(self) -> list[Data]:
        """Execute the search and return the organic results as Data objects."""
        try:
            payload = self._search()
            results = payload.get("results") or []

            data_results = [
                Data(
                    text=result.get("description", ""),
                    data={
                        "title": result.get("title", ""),
                        "link": result.get("link", ""),
                        "description": result.get("description", ""),
                        "position": result.get("position"),
                    },
                )
                for result in results
            ]
        except (httpx.HTTPError, ValueError, KeyError) as e:
            error_data = [Data(text=str(e), data={"error": str(e)})]
            self.status = error_data
            return error_data
        else:
            self.status = data_results
            return data_results

    def run_model(self) -> DataFrame:
        return self.fetch_content_dataframe()

    def fetch_content_dataframe(self) -> DataFrame:
        """Convert the search results to a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the Serply search results.
        """
        return DataFrame(self.fetch_content())
