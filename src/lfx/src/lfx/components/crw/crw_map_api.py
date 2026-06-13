from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data

# fastCRW is a Firecrawl-compatible web scraper shipped as a single binary; it can be
# self-hosted or used via the managed cloud at https://fastcrw.com. Because the API is
# Firecrawl-compatible, this component mirrors the Firecrawl Map component and points
# the Firecrawl client at the fastCRW base URL.
DEFAULT_API_URL = "https://fastcrw.com/api"


class CrwMapApi(Component):
    display_name: str = "fastCRW Map API"
    description: str = "Maps a URL and returns the results."
    name = "CrwMapApi"

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
            name="urls",
            display_name="URLs",
            required=True,
            info="List of URLs to create maps from (separated by commas or new lines).",
            tool_mode=True,
        ),
        BoolInput(
            name="ignore_sitemap",
            display_name="Ignore Sitemap",
            info="When true, the sitemap.xml file will be ignored during crawling.",
        ),
        BoolInput(
            name="sitemap_only",
            display_name="Sitemap Only",
            info="When true, only links found in the sitemap will be returned.",
        ),
        BoolInput(
            name="include_subdomains",
            display_name="Include Subdomains",
            info="When true, subdomains of the provided URL will also be scanned.",
        ),
    ]

    outputs = [
        Output(display_name="JSON", name="data", method="map"),
    ]

    def map(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        # Validate URLs
        if not self.urls:
            msg = "URLs are required"
            raise ValueError(msg)

        # Split and validate URLs (handle both commas and newlines)
        urls = [url.strip() for url in self.urls.replace("\n", ",").split(",") if url.strip()]
        if not urls:
            msg = "No valid URLs provided"
            raise ValueError(msg)

        params = {
            "ignoreSitemap": self.ignore_sitemap,
            "sitemapOnly": self.sitemap_only,
            "includeSubdomains": self.include_subdomains,
        }

        app = FirecrawlApp(api_key=self.api_key, api_url=self.api_url or DEFAULT_API_URL)

        # Map all provided URLs and combine results
        combined_links = []
        for url in urls:
            result = app.map_url(url, params=params)
            if isinstance(result, dict) and "links" in result:
                combined_links.extend(result["links"])

        map_result = {"success": True, "links": combined_links}

        return Data(data=map_result)
