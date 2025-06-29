# brightdata_search_engine.py
import urllib.parse

import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, MessageTextInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output

from .constants import HTTP_OK


class BrightDataSearchEngineComponent(Component):
    """Search Google, Bing, or Yandex using Bright Data's search scraping service."""

    display_name = "Bright Data Search Engine"
    description = "Search Google, Bing, or Yandex using Bright Data's search scraping service"
    icon = "BrightData"
    name = "BrightDataSearchEngine"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="🔑 API Token",
            required=True,
            password=True,
            info="Your Bright Data API token from account settings",
            placeholder="Enter your Bright Data API token...",
        ),
        MessageTextInput(
            name="query_input",
            display_name="🔍 Search Query Input",
            info="The search term or phrase to look for - can be connected from another component or entered manually",
            tool_mode=True,
            placeholder="Enter your search query...",
        ),
        DropdownInput(
            name="engine",
            display_name="🌐 Search Engine",
            options=["google", "bing", "yandex"],
            value="google",
            info="Choose which search engine to use for the search",
            placeholder="google, bing, yandex",
        ),
    ]

    outputs = [
        Output(display_name="Search Results", name="results", method="search_web"),
    ]

    def _build_search_url(self, engine: str, query: str) -> str:
        """Build the search URL for the specified engine."""
        encoded_query = urllib.parse.quote(query)

        if engine == "yandex":
            return f"https://yandex.com/search/?text={encoded_query}"
        if engine == "bing":
            return f"https://www.bing.com/search?q={encoded_query}"
        # default to google
        return f"https://www.google.com/search?q={encoded_query}"

    def get_query_from_input(self) -> str:
        """Extract query from the input, handling both Message and string types."""
        # Langflow automatically converts inputs to appropriate types
        # We just need to handle Message vs string cases
        if hasattr(self.query_input, "text"):
            # It's a Message object
            return str(self.query_input.text).strip()
        # It's already a string or can be converted to string
        return str(self.query_input or "").strip()

    def search_web(self) -> Data:
        """Search the web using Bright Data's search engine scraping."""
        try:
            query = self.get_query_from_input()

            if not query:
                error_msg = "Search query is required"
                return Data(text=error_msg, data={"status": "error", "error": error_msg})

            search_url = self._build_search_url(self.engine, query)

            headers = {
                "authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "url": search_url,
                "zone": "mcp_unlocker",
                "format": "raw",
                "data_format": "markdown",
            }

            response = requests.post("https://api.brightdata.com/request", json=payload, headers=headers, timeout=120)

            if response.status_code == HTTP_OK:
                results = response.text
                return Data(
                    text=results,
                    data={
                        "query": query,
                        "engine": self.engine,
                        "search_url": search_url,
                        "status": "success",
                        "results_length": len(results),
                    },
                )
            error_msg = f"Error searching: HTTP {response.status_code} - {response.text}"
            return Data(
                text=error_msg, data={"query": query, "engine": self.engine, "status": "error", "error": error_msg}
            )

        except requests.RequestException as e:
            error_msg = f"Exception occurred while searching: {e!s}"
            return Data(
                text=error_msg,
                data={
                    "query": query if "query" in locals() else "unknown",
                    "engine": self.engine,
                    "status": "error",
                    "error": error_msg,
                },
            )
