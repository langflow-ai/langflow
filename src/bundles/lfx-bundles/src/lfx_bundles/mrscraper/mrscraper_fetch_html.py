"""MrScraper Scrape HTML, retaining the existing MrscraperFetchHtml identifier."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    NO_SCREENSHOT,
    api_token_input,
    call_sdk,
    optional_text,
    page_inputs,
    page_kwargs,
    payload,
    screenshot_capture,
    url_input,
)


class MrscraperFetchHtml(Component):
    """Retrieve a page's raw HTML, optionally with a screenshot, through the SDK."""

    display_name: str = "MrScraper Scrape HTML"
    description: str = "Retrieve the raw HTML of a page. Browser rendering is optional."
    name = "MrscraperFetchHtml"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        api_token_input(),
        url_input(),
        DropdownInput(
            name="screenshot",
            display_name="Screenshot",
            options=[NO_SCREENSHOT, "full", "top"],
            value=NO_SCREENSHOT,
            combobox=True,
            info=(
                "Screenshot to capture with the HTML: None for no screenshot, full for the entire page, "
                "top for the first viewport, or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an "
                "optional -ZOOM percent from 25 to 300, such as 1280x800 or 1920x1080-75. "
                "Setting a screenshot also sends browserRendering=true."
            ),
        ),
        *page_inputs(loading=True, action=True),
    ]

    outputs = [Output(display_name="HTML", name="data", method="fetch")]

    async def fetch(self) -> Data:
        """Return the page HTML; with a screenshot, the API returns html and screenshot."""
        result = await call_sdk(
            self.api_token,
            "scrape_html",
            url=(self.url or "").strip(),
            **page_kwargs(self, loading=True),
            action=optional_text(self.action),
            screenshot=screenshot_capture(self.screenshot),
        )
        return Data(data=payload(result, scalar_key="html"))
