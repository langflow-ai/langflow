import uuid

from langflow.custom.custom_component.component import Component
from langflow.io import DataInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from langflow.schema.data import Data


class FirecrawlCrawlApi(Component):
    display_name: str = "Firecrawl Crawl API"
    description: str = "Crawls a URL and returns the results."
    name = "FirecrawlCrawlApi"

    documentation: str = "https://docs.firecrawl.dev/v1/api-reference/endpoint/crawl-post"

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
            advanced=True,
        ),
        IntInput(
            name="poll_interval",
            display_name="Poll Interval",
            info="Interval in seconds to poll for crawl status.",
            default=30,
            advanced=True,
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            info="Maximum link depth to crawl.",
            default=2,
            advanced=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum number of pages to crawl.",
            default=100,
            advanced=True,
        ),
        StrInput(
            name="idempotency_key",
            display_name="Idempotency Key",
            info="Optional idempotency key to ensure unique requests.",
            advanced=True,
        ),
        DataInput(
            name="crawlerOptions",
            display_name="Crawler Options",
            info="The crawler options to send with the request.",
            advanced=True,
        ),
        DataInput(
            name="scrapeOptions",
            display_name="Scrape Options",
            info="The page options to send with the request.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="crawl"),
    ]
    idempotency_key: str | None = None
    poll_interval: int = 30
    max_depth: int = 2
    limit: int = 100

    def crawl(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = {
            "maxDepth": self.max_depth,
            "limit": self.limit,
        }

        if self.crawlerOptions:
            params.update(self.crawlerOptions.__dict__["data"])

        if self.scrapeOptions:
            scrape_options = self.scrapeOptions.__dict__["data"]
            if scrape_options:
                params["scrapeOptions"] = scrape_options

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

        app = FirecrawlApp(api_key=self.api_key)
        crawl_status = app.crawl_url(
            self.url, params=params, idempotency_key=self.idempotency_key, poll_interval=self.poll_interval
        )
        return Data(data={"results": crawl_status})
