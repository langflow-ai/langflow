from langflow.custom import Component
from langflow.io import (
    BoolInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Data


class FirecrawlMapApi(Component):
    display_name: str = "FirecrawlMapApi"
    description: str = "Firecrawl Map API."
    name = "FirecrawlMapApi"

    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/map"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            password=True,
            info="The API key to use Firecrawl API.",
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
        Output(display_name="Data", name="data", method="map"),
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

        app = FirecrawlApp(api_key=self.api_key)

        # Map all provided URLs and combine results
        combined_links = []
        for url in urls:
            result = app.map_url(url, params=params)
            if isinstance(result, dict) and "links" in result:
                combined_links.extend(result["links"])

        map_result = {"success": True, "links": combined_links}

        return Data(data=map_result)
