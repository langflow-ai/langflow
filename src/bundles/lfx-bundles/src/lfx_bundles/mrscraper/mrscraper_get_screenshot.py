"""MrScraper Get Screenshot."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, Output
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


class MrscraperGetScreenshot(Component):
    """Capture a screenshot of the full page, the first viewport, or a custom viewport through the SDK."""

    display_name: str = "MrScraper Get Screenshot"
    description: str = (
        "Capture a base64 PNG screenshot of the full page, the first viewport, or a custom viewport. "
        "Browser rendering is always enabled."
    )
    name = "MrscraperGetScreenshot"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        api_token_input(),
        url_input(),
        DropdownInput(
            name="screenshot",
            display_name="Screenshot",
            options=["full", "top"],
            value="full",
            combobox=True,
            info=(
                "Screenshot area to capture: full for the entire scroll height, top for the first viewport, "
                "or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an optional -ZOOM percent from 25 "
                "to 300, such as 1280x800 or 1920x1080-75."
            ),
        ),
        *page_inputs(loading=False, action=False),
    ]

    outputs = [Output(display_name="Screenshot", name="data", method="capture")]

    async def capture(self) -> Data:
        """Return the screenshot and page HTML; the SDK sends html=false, markdown=false, and browserRendering=true."""
        result = await call_sdk(
            self.api_token,
            "get_screenshot",
            url=(self.url or "").strip(),
            screenshot=optional_text(self.screenshot) or "full",
            **page_kwargs(self, loading=False),
        )
        return Data(data=payload(result, scalar_key="screenshot"))
