"""MrScraper component: rerun an existing AI scraper on a new URL."""

from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperRunAiScraper(Component):
    """Langflow component wrapping MrScraper `rerun_scraper` for AI scraper jobs."""

    display_name: str = "MrScraper Run AI Scraper"
    description: str = (
        "Rerun an existing MrScraper AI scraper on a new URL. "
        "Reuses the extraction logic from a previously created AI scraper."
    )
    name = "MrscraperRunAiScraper"
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
        StrInput(
            name="scraper_id",
            display_name="Scraper ID",
            required=True,
            info="ID of the AI scraper to rerun (from create_scraper).",
            tool_mode=True,
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target URL. Can be the original URL or a different compatible page.",
            tool_mode=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            value=2,
            info="Crawl depth from the start URL (map agent only). 0 = start URL only.",
            advanced=True,
        ),
        IntInput(
            name="max_pages",
            display_name="Max Pages",
            value=50,
            info="Maximum pages to process (map agent only).",
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            value=1000,
            info="Maximum records to extract (map agent only).",
            advanced=True,
        ),
        StrInput(
            name="include_patterns",
            display_name="Include Patterns",
            info="URL regex patterns to include when following links, separated by ||. (map agent only)",
            advanced=True,
        ),
        StrInput(
            name="exclude_patterns",
            display_name="Exclude Patterns",
            info="URL regex patterns to skip when following links, separated by ||. (map agent only)",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="rerun"),
    ]

    async def rerun(self) -> Data:
        """Rerun an AI scraper and return the API response as `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        max_depth = 2 if self.max_depth is None else self.max_depth
        max_pages = 50 if self.max_pages is None else self.max_pages
        limit = 1000 if self.limit is None else self.limit

        client = MrScraper(token=self.api_token)
        result = await client.rerun_scraper(
            scraper_id=self.scraper_id,
            url=self.url,
            max_depth=max_depth,
            max_pages=max_pages,
            limit=limit,
            include_patterns=self.include_patterns or "",
            exclude_patterns=self.exclude_patterns or "",
        )
        return Data(data=result)
