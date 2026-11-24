"""MrScraper Scrape Brand."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import api_token_input, call_sdk, payload, url_input


class MrscraperScrapeBrand(Component):
    """Extract a website's brand identity through the SDK."""

    display_name: str = "MrScraper Scrape Brand"
    description: str = "Extract a website's colors, typography, logos, and social links as JSON."
    name = "MrscraperScrapeBrand"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input(), url_input()]

    outputs = [Output(display_name="Brand", name="data", method="extract_brand")]

    async def extract_brand(self) -> Data:
        """Return the brand job; the SDK sends action=brand-scraping and bundle=none."""
        result = await call_sdk(self.api_token, "scrape_brand", url=(self.url or "").strip())
        return Data(data=payload(result))
