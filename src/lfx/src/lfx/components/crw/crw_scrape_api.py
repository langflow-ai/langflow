from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data

# fastCRW is a Firecrawl-compatible web scraper shipped as a single binary; it can be
# self-hosted or used via the managed cloud at https://fastcrw.com. Because the API is
# Firecrawl-compatible, this component mirrors the Firecrawl Scrape component and points
# the Firecrawl client at the fastCRW base URL.
DEFAULT_API_URL = "https://fastcrw.com/api"


class CrwScrapeApi(Component):
    display_name: str = "fastCRW Scrape API"
    description: str = "Scrapes a URL and returns the results."
    name = "CrwScrapeApi"

    documentation: str = "https://fastcrw.com/docs/rest-api"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="fastCRW API Key",
            required=False,
            password=True,
            info="The API key to use fastCRW API. Optional for self-hosted instances without auth.",
        ),
        StrInput(
            name="api_url",
            display_name="API URL",
            info="The base URL of the fastCRW API. Override for self-hosted instances.",
            value=DEFAULT_API_URL,
            advanced=True,
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL to scrape.",
            tool_mode=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in milliseconds for the request.",
        ),
        DataInput(
            name="scrapeOptions",
            display_name="Scrape Options",
            info="The page options to send with the request.",
        ),
        DataInput(
            name="extractorOptions",
            display_name="Extractor Options",
            info="The extractor options to send with the request.",
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="scrape"),
    ]

    def scrape(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = self.scrapeOptions.__dict__.get("data", {}) if self.scrapeOptions else {}
        extractor_options_dict = self.extractorOptions.__dict__.get("data", {}) if self.extractorOptions else {}
        if extractor_options_dict:
            params["extract"] = extractor_options_dict

        # Set default values for parameters
        params.setdefault("formats", ["markdown"])  # Default output format
        params.setdefault("onlyMainContent", True)  # Default to only main content

        app = FirecrawlApp(api_key=self.api_key, api_url=self.api_url or DEFAULT_API_URL)
        results = app.scrape_url(self.url, params=params)
        return Data(data=results)
