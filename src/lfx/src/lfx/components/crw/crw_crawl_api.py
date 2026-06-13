import uuid

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

# fastCRW is a Firecrawl-compatible web scraper shipped as a single binary; it can be
# self-hosted or used via the managed cloud at https://fastcrw.com. Because the API is
# Firecrawl-compatible, this component mirrors the Firecrawl Crawl component and points
# the Firecrawl client at the fastCRW base URL.
DEFAULT_API_URL = "https://fastcrw.com/api"


class CrwCrawlApi(Component):
    display_name: str = "fastCRW Crawl API"
    description: str = "Crawls a URL and returns the results."
    name = "CrwCrawlApi"

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
        StrInput(
            name="idempotency_key",
            display_name="Idempotency Key",
            info="Optional idempotency key to ensure unique requests.",
        ),
        DataInput(
            name="crawlerOptions",
            display_name="Crawler Options",
            info="The crawler options to send with the request.",
        ),
        DataInput(
            name="scrapeOptions",
            display_name="Scrape Options",
            info="The page options to send with the request.",
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="crawl"),
    ]
    idempotency_key: str | None = None

    def crawl(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = self.crawlerOptions.__dict__["data"] if self.crawlerOptions else {}
        scrape_options_dict = self.scrapeOptions.__dict__["data"] if self.scrapeOptions else {}
        if scrape_options_dict:
            params["scrapeOptions"] = scrape_options_dict

        # Set default values for new parameters in v1
        params.setdefault("maxDepth", 2)
        params.setdefault("limit", 10000)
        params.setdefault("allowExternalLinks", False)
        params.setdefault("allowBackwardLinks", False)
        params.setdefault("ignoreSitemap", False)
        params.setdefault("ignoreQueryParameters", False)

        # Ensure onlyMainContent is explicitly set if not provided
        if "scrapeOptions" in params:
            params["scrapeOptions"].setdefault("onlyMainContent", True)
        else:
            params["scrapeOptions"] = {"onlyMainContent": True}

        if not self.idempotency_key:
            self.idempotency_key = str(uuid.uuid4())

        app = FirecrawlApp(api_key=self.api_key, api_url=self.api_url or DEFAULT_API_URL)
        crawl_result = app.crawl_url(self.url, params=params, idempotency_key=self.idempotency_key)
        return Data(data={"results": crawl_result})
