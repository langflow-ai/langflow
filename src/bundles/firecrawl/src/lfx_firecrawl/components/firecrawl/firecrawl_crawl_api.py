import re

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, IntInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _to_snake_case_kwargs(params: dict) -> dict:
    """Convert camelCase option keys to snake_case keyword arguments.

    The firecrawl-py v1 convention uses camelCase, while the v2 SDK expects
    snake_case keyword arguments. Keys that are already snake_case are passed
    through unchanged.
    """
    return {_CAMEL_TO_SNAKE_RE.sub("_", key).lower(): value for key, value in params.items()}


class FirecrawlCrawlApi(Component):
    display_name: str = "Firecrawl Crawl API"
    description: str = "Crawls a URL and returns the results."
    name = "FirecrawlCrawlApi"

    documentation: str = "https://docs.firecrawl.dev/v1/api-reference/endpoint/crawl-post"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Firecrawl API Key",
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
            from firecrawl import Firecrawl
            from firecrawl.v2.types import ScrapeOptions
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = dict(self.crawlerOptions.__dict__.get("data", {})) if self.crawlerOptions else {}
        scrape_options_dict = dict(self.scrapeOptions.__dict__.get("data", {})) if self.scrapeOptions else {}

        # Set default values for crawl parameters.
        # Note: firecrawl-py v2 renamed several options. "maxDepth" -> "max_discovery_depth"
        # and "allowBackwardLinks" -> "crawl_entire_domain".
        params.setdefault("maxDepth", 2)
        params.setdefault("limit", 10000)
        params.setdefault("allowExternalLinks", False)
        params.setdefault("allowBackwardLinks", False)
        params.setdefault("ignoreQueryParameters", False)

        # Ensure onlyMainContent is explicitly set if not provided.
        scrape_options_dict.setdefault("onlyMainContent", True)

        # Translate legacy v1 camelCase option names to the firecrawl-py v2 keyword args.
        kwargs = _to_snake_case_kwargs(params)
        if "max_depth" in kwargs:
            kwargs["max_discovery_depth"] = kwargs.pop("max_depth")
        if "allow_backward_links" in kwargs:
            kwargs["crawl_entire_domain"] = kwargs.pop("allow_backward_links")
        # v2 removed "ignore_sitemap"; it is now the "sitemap" mode enum.
        if kwargs.pop("ignore_sitemap", False):
            kwargs["sitemap"] = "skip"

        # Build the typed ScrapeOptions object expected by v2 from the (snake_cased) dict.
        scrape_kwargs = _to_snake_case_kwargs(scrape_options_dict)
        kwargs["scrape_options"] = ScrapeOptions(**scrape_kwargs)

        app = Firecrawl(api_key=self.api_key)
        # v2 polls to completion and returns a typed CrawlJob object.
        crawl_job = app.crawl(self.url, **kwargs)
        return Data(data={"results": crawl_job.model_dump()})
