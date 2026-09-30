import re

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _to_snake_case_kwargs(params: dict) -> dict:
    """Convert camelCase option keys to snake_case keyword arguments.

    The firecrawl-py v1 convention uses camelCase, while the v2 SDK expects
    snake_case keyword arguments. Keys that are already snake_case are passed
    through unchanged.
    """
    return {_CAMEL_TO_SNAKE_RE.sub("_", key).lower(): value for key, value in params.items()}


class FirecrawlScrapeApi(Component):
    display_name: str = "Firecrawl Scrape API"
    description: str = "Scrapes a URL and returns the results."
    name = "FirecrawlScrapeApi"

    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/scrape"

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
            from firecrawl import Firecrawl
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        params = dict(self.scrapeOptions.__dict__.get("data", {})) if self.scrapeOptions else {}

        # Set default values for parameters
        params.setdefault("formats", ["markdown"])  # Default output format
        params.setdefault("onlyMainContent", True)  # Default to only main content
        if self.timeout:
            params.setdefault("timeout", self.timeout)

        kwargs = _to_snake_case_kwargs(params)

        # In firecrawl-py v2, structured extraction is requested via a "json" format entry
        # on the scrape call rather than a separate extractor option.
        extractor_options_dict = self.extractorOptions.__dict__.get("data", {}) if self.extractorOptions else {}
        if extractor_options_dict:
            formats = list(kwargs.get("formats", []))
            formats.append({"type": "json", **_to_snake_case_kwargs(extractor_options_dict)})
            kwargs["formats"] = formats

        app = Firecrawl(api_key=self.api_key)
        document = app.scrape(self.url, **kwargs)
        # v2 returns a typed Document object; serialize to a dict for downstream consumers.
        return Data(data=document.model_dump())
