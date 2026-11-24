"""MrScraper Web Search."""

from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import IntInput, MultilineInput, Output, StrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    api_token_input,
    call_sdk,
    optional_text,
    payload,
    require_updated_node,
)


class MrscraperWebSearch(Component):
    """Search the web through the SDK."""

    display_name: str = "MrScraper Web Search"
    description: str = "Search the web and return ranked results with titles, URLs, descriptions, and sources."
    name = "MrscraperWebSearch"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        api_token_input(),
        MultilineInput(
            name="query",
            display_name="Search Query",
            required=True,
            tool_mode=True,
            info="Search query text, trimmed before sending, containing 1 to 1000 characters.",
        ),
        StrInput(
            name="country",
            display_name="Country",
            value="",
            info=(
                "Two-letter country code to search from, sent in lowercase. "
                "Leave blank to use the API default (United States)."
            ),
        ),
        IntInput(
            name="num_results",
            display_name="Number of Results",
            value=10,
            range_spec=RangeSpec(step_type="int", min=10, max=100, step=1),
            info="Number of search results to request, as an integer from 10 to 100. Fewer results may be returned.",
        ),
    ]

    outputs = [Output(display_name="Search Results", name="data", method="search")]

    async def search(self) -> Data:
        """Run a web search through the SDK and return its response payload."""
        require_updated_node(self, "raw")
        result = await call_sdk(
            self.api_token,
            "web_search",
            query=self.query,
            country=optional_text(self.country),
            num_results=self.num_results,
        )
        return Data(data=payload(result))
