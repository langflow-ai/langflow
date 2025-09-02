from langflow.custom.custom_component.component import Component
from langflow.io import (
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema.data import Data


class FirecrawlMapApi(Component):
    display_name: str = "Firecrawl Map API"
    description: str = "Maps a URL and returns the results."
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
            name="url",
            display_name="URL",
            required=True,
            info="The starting URL for URL discovery.",
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="Maximum number of URLs to return.",
            default=50,
            advanced=True,
        ),
        StrInput(
            name="search",
            display_name="Search Term",
            info="Optional search term to filter URLs.",
            advanced=True,
        ),
        BoolInput(
            name="ignoreSitemap",
            display_name="Ignore Sitemap",
            info="Skip sitemap.xml discovery and only use HTML links.",
            default=False,
            advanced=True,
        ),
        BoolInput(
            name="sitemapOnly",
            display_name="Sitemap Only",
            info="Only use sitemap.xml for discovery, ignore HTML links.",
            default=False,
            advanced=True,
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

        params = {
            "limit": self.limit,
        }

        app = FirecrawlApp(api_key=self.api_key)
        map_result = app.map_url(self.url, params=params)
        return Data(data=map_result)
