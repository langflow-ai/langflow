from langflow.custom import Component
from langflow.io import (
    DataInput,
    IntInput,
    MultilineInput,
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
            default=30000,
            advanced=True,
        ),
        IntInput(
            name="waitFor",
            display_name="Wait For",
            info="Time in milliseconds to wait for dynamic content to load.",
            default=1000,
            advanced=True,
        ),
        DataInput(
            name="scrapeOptions",
            display_name="Scrape Options",
            info="The page options to send with the request.",
            advanced=True,
        ),
        DataInput(  # https://docs.firecrawl.dev/features/extract
            name="extractorOptions",
            display_name="Extractor Options",
            info="The extractor options to send with the request.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="crawl"),
    ]
    
    timeout: int = 30000
    waitFor: int = 1000

    def crawl(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = {
            "timeout": self.timeout,
            "waitFor": self.waitFor,
        }
        
        if self.scrapeOptions:
            params.update(self.scrapeOptions.__dict__["data"])
        
        if self.extractorOptions:
            extract_options = self.extractorOptions.__dict__["data"]
            if extract_options:
                params["extract"] = extract_options

        app = FirecrawlApp(api_key=self.api_key)
        scrape_result = app.scrape_url(self.url, params=params)
        return Data(data=scrape_result)
