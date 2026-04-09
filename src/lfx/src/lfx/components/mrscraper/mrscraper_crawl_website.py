"""MrScraper component: crawl sub-pages with the map agent."""

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperCrawlWebsite(Component):
    """Langflow component for site-wide crawling via MrScraper map agent settings."""

    display_name: str = "MrScraper Crawl Website"
    description: str = (
        "Crawl all sub-pages of a website using MrScraper's map agent. "
        "Automatically discovers and scrapes pages from the given starting URL."
    )
    name = "MrscraperCrawlWebsite"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        SecretStrInput(
            name="api_token",
            display_name="MrScraper API Token",
            required=True,
            password=True,
            info="Your MrScraper API token. Get yours at https://app.mrscraper.com.",
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Starting URL to crawl.",
            tool_mode=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            value=2,
            info="Crawl depth from the start URL. 0 = start URL only.",
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            value=50,
            info="Maximum number of pages to process.",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=1000,
            info="Maximum number of records to extract.",
        ),
        StrInput(
            name="include_patterns",
            display_name="Include Patterns",
            info='URL regex patterns to include when following links, separated by "||".',
            advanced=True,
        ),
        StrInput(
            name="exclude_patterns",
            display_name="Exclude Patterns",
            info='URL regex patterns to skip when following links, separated by "||".',
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="crawl"),
    ]

    async def crawl(self) -> Data:
        """Start a map-agent crawl from the given URL and return API `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        max_depth = 2 if self.max_depth is None else self.max_depth
        max_pages = 50 if self.max_pages is None else self.max_pages
        limit = 1000 if self.limit is None else self.limit

        client = MrScraper(token=self.api_token)
        result = await client.create_scraper(
            url=self.url,
            message="",
            agent="map",
            max_depth=max_depth,
            max_pages=max_pages,
            limit=limit,
            include_patterns=self.include_patterns or "",
            exclude_patterns=self.exclude_patterns or "",
        )
        return Data(data=result)
