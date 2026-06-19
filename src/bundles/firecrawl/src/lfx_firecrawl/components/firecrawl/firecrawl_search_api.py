from lfx.custom.custom_component.component import Component
from lfx.io import (
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data


class FirecrawlSearchApi(Component):
    display_name: str = "Firecrawl Search API"
    description: str = "Searches the web and returns the results."
    name = "FirecrawlSearchApi"

    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/search"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firecrawl API Key",
            required=True,
            password=True,
            info="The API key to use Firecrawl API.",
        ),
        MultilineInput(
            name="query",
            display_name="Query",
            required=True,
            info="The search query to run.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum number of results to return.",
            value=5,
        ),
        StrInput(
            name="location",
            display_name="Location",
            info="Location to bias the search results (e.g. a country or region).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="search"),
    ]

    def search(self) -> Data:
        try:
            from firecrawl import Firecrawl
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        if not self.query:
            msg = "Query is required"
            raise ValueError(msg)

        kwargs: dict = {}
        if self.limit:
            kwargs["limit"] = self.limit
        if self.location:
            kwargs["location"] = self.location

        app = Firecrawl(api_key=self.api_key)
        result = app.search(self.query, **kwargs)

        # v2 returns a typed SearchData object (results grouped by source);
        # serialize to a dict for downstream consumers.
        search_result = result.model_dump() if hasattr(result, "model_dump") else result

        return Data(data=search_result)
