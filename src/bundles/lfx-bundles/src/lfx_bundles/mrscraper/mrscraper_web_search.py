"""MrScraper component: real-time web search results from a query."""

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import FloatInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import call_sdk, payload


class MrscraperWebSearch(Component):
    """Search the web through MrScraper."""

    display_name: str = "MrScraper Web Search"
    description: str = "Search the web for real-time results: website URLs, titles, and descriptions."
    name = "MrscraperWebSearch"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="MrScraper API Token",
            required=True,
            password=True,
            info="Your MrScraper API token from https://app.mrscraper.com.",
        ),
        MultilineInput(
            name="query",
            display_name="Search Query",
            required=True,
            tool_mode=True,
            info="The search query.",
        ),
        StrInput(
            name="country",
            display_name="Country",
            value="",
            info='Optional country code for localized results, for example "us". Leave empty for the API default.',
        ),
        IntInput(
            name="num_results",
            display_name="Number of Results",
            value=10,
            range_spec=RangeSpec(min=10, max=100, step_type="int"),
            info="Number of results to return, from 10 to 100.",
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=600.0,
            advanced=True,
            info="Positive HTTP request timeout in seconds.",
        ),
    ]

    outputs = [Output(display_name="Search Results", name="data", method="search")]

    async def search(self) -> Data:
        """Run a web search through the SDK and return its response payload."""
        result = await call_sdk(
            self.api_token,
            "web_search",
            query=self.query,
            country=(self.country or "").strip() or None,
            num_results=self.num_results,
            timeout=self.timeout,
        )
        return Data(data=payload(result, scalar_key="result"))
