"""MrScraper component: fetch rendered HTML via the stealth browser."""

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperFetchHtml(Component):
    """Langflow component wrapping MrScraper `fetch_html` for JS-rendered pages."""

    display_name: str = "MrScraper Fetch Rendered HTML"
    description: str = (
        "Fetch the fully rendered HTML of a page via the MrScraper stealth browser. "
        "Handles JavaScript rendering and bot-detection evasion."
    )
    name = "MrscraperFetchHtml"
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
            info="Target URL to fetch rendered HTML from.",
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=120,
            info="Maximum seconds to wait for the page to load.",
            advanced=True,
        ),
        StrInput(
            name="geo_code",
            display_name="Geo Code",
            value="US",
            info='ISO country code for proxy geolocation (e.g. "US", "GB", "ID", "SG").',
            advanced=True,
        ),
        BoolInput(
            name="block_resources",
            display_name="Block Resources",
            value=False,
            info="Block images, CSS, and fonts to speed up the request.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="HTML", name="data", method="fetch"),
    ]

    async def fetch(self) -> Data:
        """Fetch rendered HTML for the target URL and return `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        client = MrScraper(token=self.api_token)
        result = await client.fetch_html(
            url=self.url,
            timeout=self.timeout or 120,
            geo_code=self.geo_code or "US",
            block_resources=self.block_resources,
        )
        return Data(data=result)
