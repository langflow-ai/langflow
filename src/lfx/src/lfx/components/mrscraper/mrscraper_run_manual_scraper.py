"""MrScraper component: rerun a manual (selector-based) scraper on a new URL."""

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperRunManualScraper(Component):
    """Langflow component wrapping MrScraper `rerun_manual_scraper`."""

    display_name: str = "MrScraper Run Manual Scraper"
    description: str = (
        "Rerun a manually configured MrScraper scraper on a new URL. "
        "Use for scrapers built with custom CSS selectors or XPath rules in the MrScraper dashboard."
    )
    name = "MrscraperRunManualScraper"
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
            info="ID of the manual scraper (from the MrScraper dashboard).",
            tool_mode=True,
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="Target URL. The page structure should match the original scraper's target.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="rerun_manual"),
    ]

    async def rerun_manual(self) -> Data:
        """Rerun a manual scraper configuration and return `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        client = MrScraper(token=self.api_token)
        result = await client.rerun_manual_scraper(
            scraper_id=self.scraper_id,
            url=self.url,
        )
        return Data(data=result)
