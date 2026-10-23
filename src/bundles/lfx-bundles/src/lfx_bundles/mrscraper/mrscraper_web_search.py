"""MrScraper component: Google search results from query text or a URL."""

import math

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FloatInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import call_sdk, optional_integer, payload


class MrscraperWebSearch(Component):
    """Search Google through the MrScraper v2 synchronous SERP API."""

    display_name: str = "MrScraper Web Search"
    description: str = (
        "Search the web to retrieve real-time search results, including relevant website URLs, titles, "
        "descriptions, and related questions based on a given query or a full Google search URL."
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
            display_name="Query or Google URL",
            required=True,
            tool_mode=True,
            info="Search text or a Google URL containing q, gl, hl, and start parameters.",
        ),
        BoolInput(
            name="raw",
            display_name="Raw HTML",
            value=True,
            info="Return HTML regardless of Format. Disable this to request JSON results.",
        ),
        DropdownInput(name="format", display_name="Format", options=["json", "html"], value="json"),
        StrInput(name="region", display_name="Region", advanced=True, info="Overrides gl from the Google URL."),
        StrInput(name="language", display_name="Language", advanced=True, info="Overrides hl from the Google URL."),
        StrInput(
            name="page",
            display_name="Page",
            value="",
            advanced=True,
            info="Optional one-based page. Leave empty to use start from a Google URL or the API default.",
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
