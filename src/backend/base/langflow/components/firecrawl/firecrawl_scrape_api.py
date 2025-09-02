from langflow.custom.custom_component.component import Component
from langflow.io import (
    BoolInput,
    DataInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema.data import Data


class FirecrawlScrapeApi(Component):
    display_name: str = "Firecrawl Scrape API"
    description: str = "Scrapes a URL and returns the results."
    name = "FirecrawlScrapeApi"

    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/scrape"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            password=True,
            info="The API key to use Firecrawl API.",
        ),
        MultilineInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL to scrape.",
            tool_mode=True,
        ),
        DataInput(
            name="scrapeOptions",
            display_name="Scrape Options",
            info="The page options to send with the request.",
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout in seconds for the request.",
            default=300,
            advanced=True,
        ),
        BoolInput(
            name="ignoreSitemap",
            display_name="Ignore Sitemap",
            info="Skip sitemap.xml discovery for URL extraction.",
            default=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="scrape"),
    ]

    def scrape(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = {}

        if self.scrapeOptions:
            params.update(self.scrapeOptions.__dict__["data"])

        app = FirecrawlApp(api_key=self.api_key)
        scrape_result = app.scrape_url(self.url, params=params)
        return Data(data=scrape_result)
