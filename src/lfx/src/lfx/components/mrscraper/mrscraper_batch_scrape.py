"""MrScraper component: batch rerun AI or manual scrapers on multiple URLs."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperBatchScrape(Component):
    """Langflow component for MrScraper bulk AI or manual scraper reruns."""

    display_name: str = "MrScraper Batch Scrape URLs"
    description: str = (
        "Rerun an existing MrScraper scraper on multiple URLs in a single batch. "
        "Supports both AI and Manual scraper modes."
    )
    name = "MrscraperBatchScrape"
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
            info="ID of the scraper to rerun (from create_scraper or the MrScraper dashboard).",
            tool_mode=True,
        ),
        MultilineInput(
            name="urls",
            display_name="URLs",
            required=True,
            info="List of target URLs to scrape (separated by commas or new lines).",
            tool_mode=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Scraper Mode",
            options=["AI", "Manual"],
            value="AI",
            info='"AI" uses bulk_rerun_ai_scraper. "Manual" uses bulk_rerun_manual_scraper.',
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="batch_scrape"),
    ]

    async def batch_scrape(self) -> Data:
        """Validate URLs, dispatch bulk rerun by mode, and return `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        if not self.urls:
            msg = "URLs are required"
            raise ValueError(msg)

        url_list = [u.strip() for u in self.urls.replace("\n", ",").split(",") if u.strip()]
        if not url_list:
            msg = "No valid URLs provided"
            raise ValueError(msg)

        client = MrScraper(token=self.api_token)

        if self.mode == "AI":
            result = await client.bulk_rerun_ai_scraper(
                scraper_id=self.scraper_id,
                urls=url_list,
            )
        else:
            result = await client.bulk_rerun_manual_scraper(
                scraper_id=self.scraper_id,
                urls=url_list,
            )

        return Data(data=result)
