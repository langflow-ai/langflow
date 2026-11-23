"""MrScraper Scrape JSON."""

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MultilineInput, Output
from lfx.schema.data import Data

from lfx_bundles.mrscraper.mrscraper_common import (
    DEFAULT_JSON_PROMPT,
    api_token_input,
    call_sdk,
    page_inputs,
    page_kwargs,
    payload,
    url_input,
)


class MrscraperScrapeJson(Component):
    """Extract structured JSON from one page through the SDK."""

    display_name: str = "MrScraper Scrape JSON"
    description: str = (
        "Extract structured JSON from a page using a natural-language prompt. "
        "Append Json Schema: and a JSON schema to shape the output."
    )
    name = "MrscraperScrapeJson"
    icon: str = "MrScraper"
    documentation: str = "https://docs.mrscraper.com"

    inputs = [
        api_token_input(),
        url_input(),
        MultilineInput(
            name="prompt",
            display_name="Prompt",
            value=DEFAULT_JSON_PROMPT,
            tool_mode=True,
            info=(
                "Instructions describing the data to extract. "
                "Append Json Schema: and a JSON schema to shape the output."
            ),
        ),
        BoolInput(
            name="html",
            display_name="Include HTML",
            value=True,
            advanced=True,
            info="Whether to include the page HTML in the response.",
        ),
        *page_inputs(loading=True, action=False),
        BoolInput(
            name="screenshot",
            display_name="Include Screenshot",
            value=False,
            advanced=True,
            info="Whether to include a base64 screenshot in the response.",
        ),
    ]

    outputs = [Output(display_name="Extracted Data", name="data", method="extract")]

    async def extract(self) -> Data:
        """Return the extraction result; the SDK sends agent=general and switches to POST for long prompts."""
        result = await call_sdk(
            self.api_token,
            "scrape_json",
            url=(self.url or "").strip(),
            prompt=self.prompt or DEFAULT_JSON_PROMPT,
            html=self.html,
            **page_kwargs(self, loading=True),
            screenshot=self.screenshot,
        )
        return Data(data=payload(result))
