"""MrScraper Scrape Markdown."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    api_token_input,
    call_sdk,
    optional_text,
    page_inputs,
    page_kwargs,
    payload,
    url_input,
)


class MrscraperScrapeMarkdown(Component):
    """Retrieve a page as clean Markdown through the SDK."""

    display_name: str = "MrScraper Scrape Markdown"
    description: str = "Retrieve a page as clean Markdown. Browser rendering is optional."
    name = "MrscraperScrapeMarkdown"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input(), url_input(), *page_inputs(loading=True, action=True)]

    outputs = [Output(display_name="Markdown", name="data", method="scrape")]

    async def scrape(self) -> Data:
        """Return the page Markdown under the markdown field."""
        result = await call_sdk(
            self.api_token,
            "scrape_markdown",
            url=(self.url or "").strip(),
            **page_kwargs(self, loading=True),
            action=optional_text(self.action),
        )
        return Data(data=payload(result, scalar_key="markdown"))
