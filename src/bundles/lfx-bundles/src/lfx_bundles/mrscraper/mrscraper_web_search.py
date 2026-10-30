"""MrScraper component: real-time web search results from a query."""

import math

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FloatInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import call_sdk, optional_integer, payload


class MrscraperWebSearch(Component):
    """Search the web through MrScraper."""

    display_name: str = "MrScraper Web Search"
    description: str = (
        "Search the web to retrieve real-time search results, including relevant website URLs, titles, "
        "descriptions, and related questions based on a given query."
    )
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
            name="url",
            display_name="Search Query",
            required=True,
            tool_mode=True,
            info="The search query.",
        ),
        BoolInput(
            name="raw",
            display_name="Raw HTML",
            value=True,
            info="Return HTML regardless of Format. Disable this to request JSON results.",
        ),
        DropdownInput(name="format", display_name="Format", options=["json", "html"], value="json"),
        StrInput(name="region", display_name="Region", advanced=True, info="Optional country code for search results."),
        StrInput(
            name="language", display_name="Language", advanced=True, info="Optional language code for search results."
        ),
        StrInput(
            name="page",
            display_name="Page",
            value="",
            advanced=True,
            info="Optional results page number, starting at 1.",
        ),
        BoolInput(name="render_js", display_name="Render JavaScript", value=False, advanced=True),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=600.0, advanced=True),
    ]

    outputs = [Output(display_name="Search Results", name="data", method="search")]

    async def search(self) -> Data:
        """Normalize search input through the SDK and return its response payload."""
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            msg = "timeout must be greater than 0 seconds"
            raise ValueError(msg)
        result = await call_sdk(
            self.api_token,
            "web_search",
            url=self.url,
            raw=self.raw,
            format=self.format,
            region=self.region or None,
            language=self.language or None,
            page=optional_integer(self.page, name="page"),
            render_js=self.render_js,
            timeout=self.timeout,
        )
        return Data(data=payload(result, scalar_key="result"))
