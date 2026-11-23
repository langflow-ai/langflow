"""MrScraper Get Screenshot."""

from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    api_token_input,
    call_sdk,
    page_inputs,
    page_kwargs,
    payload,
    url_input,
)


class MrscraperGetScreenshot(Component):
    """Capture a full-page screenshot through the SDK."""

    display_name: str = "MrScraper Get Screenshot"
    description: str = "Capture a base64 PNG screenshot of the full page. Browser rendering is always enabled."
    name = "MrscraperGetScreenshot"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [api_token_input(), url_input(), *page_inputs(loading=False, action=False)]

    outputs = [Output(display_name="Screenshot", name="data", method="capture")]

    async def capture(self) -> Data:
        """Return the screenshot and page HTML; the SDK sends screenshot=full, html=false, and markdown=false."""
        result = await call_sdk(
            self.api_token,
            "get_screenshot",
            url=(self.url or "").strip(),
            **page_kwargs(self, loading=False),
        )
        return Data(data=payload(result, scalar_key="screenshot"))
