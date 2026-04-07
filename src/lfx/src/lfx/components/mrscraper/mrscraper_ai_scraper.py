"""MrScraper component: create and run an AI-powered scraper via the official SDK."""

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data


class MrscraperAiScraper(Component):
    """Langflow component wrapping MrScraper `create_scraper` for natural-language extraction."""

    display_name: str = "MrScraper AI Agent Scraper"
    description: str = (
        "Create and run an AI-powered scraper using MrScraper. "
        "Uses natural-language instructions to extract data from any web page."
    )
    name = "MrscraperAiScraper"
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
            info="Target URL to scrape.",
            tool_mode=True,
        ),
        MultilineInput(
            name="message",
            display_name="Extraction Prompt",
            required=True,
            info=(
                "Natural-language description of what to extract. "
                'Example: "Extract all product names, prices, and ratings".'
            ),
            tool_mode=True,
        ),
        DropdownInput(
            name="agent",
            display_name="Agent Type",
            options=["general", "listing", "map"],
            value="general",
            info=(
                '"general" works on almost any page. "listing" is optimised for listing/grid pages. '
                '"map agent" is optimised for map pages.'
            ),
        ),
        StrInput(
            name="proxy_country",
            display_name="Proxy Country",
            info='ISO country code for proxy geolocation (e.g. "us", "gb", "sg"). Optional.',
        ),
    ]

    outputs = [
        Output(display_name="Result", name="data", method="run_scraper"),
    ]

    async def run_scraper(self) -> Data:
        """Call the MrScraper API to create a scraper run and return structured `Data`."""
        try:
            from mrscraper import MrScraper
        except ImportError as e:
            msg = "Could not import mrscraper SDK. Please install it with `pip install mrscraper-sdk`."
            raise ImportError(msg) from e

        client = MrScraper(token=self.api_token)
        result = await client.create_scraper(
            url=self.url,
            message=self.message,
            agent=self.agent,
            proxy_country=self.proxy_country or "None",
        )
        return Data(data=result)
