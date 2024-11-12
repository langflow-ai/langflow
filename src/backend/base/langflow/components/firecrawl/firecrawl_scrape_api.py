from langflow.custom import Component
from langflow.io import (
    DataInput,
    IntInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data


class FirecrawlScrapeApi(Component):
    display_name: str = "FirecrawlScrapeApi"
    description: str = "Firecrawl Scrape API."
    name = "FirecrawlScrapeApi"

    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/scrape"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            password=True,
            info="The API key to use Firecrawl API.",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL to scrape.",
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
        DataInput(  # https://docs.firecrawl.dev/features/extract
            name="extractorOptions",
            display_name="Extractor Options",
            info="The extractor options to send with the request.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="crawl"),
    ]

    def crawl(self) -> list[Data]:
        try:
            from firecrawl.firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = self.scrapeOptions.__dict__["data"] if self.scrapeOptions else {}
        extractor_options_dict = self.extractorOptions.__dict__["data"] if self.extractorOptions else {}
        if extractor_options_dict:
            params["extract"] = extractor_options_dict

        app = FirecrawlApp(api_key=self.api_key)
        results = app.scrape_url(self.url, params=params)
        return Data(data=results)
