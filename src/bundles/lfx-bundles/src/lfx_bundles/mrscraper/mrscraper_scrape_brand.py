"""MrScraper Scrape Brand."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    api_token_input,
    call_sdk,
    geo_code_input,
    optional_integer,
    optional_text,
    optional_timeout_input,
    payload,
    url_input,
    warm_start_input,
)


class MrscraperScrapeBrand(Component):
    """Extract a website's brand identity through the SDK."""

    display_name: str = "MrScraper Scrape Brand"
    description: str = "Extract a website's colors, typography, logos, and social links as JSON."
    name = "MrscraperScrapeBrand"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input(), url_input(), optional_timeout_input(), warm_start_input(), geo_code_input()]

    outputs = [Output(display_name="Brand", name="data", method="extract_brand")]

    async def extract_brand(self) -> Data:
        """Return the brand job; the SDK sends action=brand-scraping and bundle=none."""
        result = await call_sdk(
            self.api_token,
            "scrape_brand",
            url=(self.url or "").strip(),
            timeout=optional_integer(self.timeout, name="timeout"),
            warm_start=self.warm_start,
            geo_code=optional_text(self.geo_code),
        )
        return Data(data=payload(result))
