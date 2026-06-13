from lfx.custom.custom_component.component import Component
from lfx.io import (
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data

# fastCRW is a Firecrawl-compatible web scraper shipped as a single binary; it can be
# self-hosted or used via the managed cloud at https://fastcrw.com. Because the API is
# Firecrawl-compatible, this component mirrors the Firecrawl provider style and points
# the Firecrawl client at the fastCRW base URL. Search is cloud-only.
DEFAULT_API_URL = "https://fastcrw.com/api"


class CrwSearchApi(Component):
    display_name: str = "fastCRW Search API"
    description: str = "Searches the web and returns the results."
    name = "CrwSearchApi"

    documentation: str = "https://fastcrw.com/docs/rest-api"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="fastCRW API Key",
            required=False,
            password=True,
            info="The API key to use fastCRW API. Optional for self-hosted instances without auth.",
        ),
        StrInput(
            name="api_url",
            display_name="API URL",
            info="The base URL of the fastCRW API. Override for self-hosted instances.",
            value=DEFAULT_API_URL,
            advanced=True,
        ),
        MultilineInput(
            name="query",
            display_name="Query",
            required=True,
            info="The search query.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="The maximum number of results to return.",
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="search"),
    ]

    def search(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        # Validate query
        if not self.query:
            msg = "Query is required"
            raise ValueError(msg)

        params = {}
        if self.limit:
            params["limit"] = self.limit

        app = FirecrawlApp(api_key=self.api_key, api_url=self.api_url or DEFAULT_API_URL)
        results = app.search(self.query, params=params)
        return Data(data=results)
