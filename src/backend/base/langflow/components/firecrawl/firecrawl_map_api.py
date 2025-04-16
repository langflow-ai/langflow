from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataInput,
    IntInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
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
        BoolInput(
            name="includeSubdomains",
            display_name="Include Subdomains",
            info="Include URLs from subdomains in results.",
            default=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="map_url"),
    ]
    
    limit: int = 50
    search: str | None = None
    ignoreSitemap: bool = False
    sitemapOnly: bool = False
    includeSubdomains: bool = False

    def map_url(self) -> Data:
        try:
            from firecrawl import FirecrawlApp
        except ImportError as e:
            msg = "Could not import firecrawl integration package. Please install it with `pip install firecrawl-py`."
            raise ImportError(msg) from e

        # Build parameters for API request
        params = {
            "limit": self.limit,
            "ignoreSitemap": self.ignoreSitemap,
            "sitemapOnly": self.sitemapOnly,
            "includeSubdomains": self.includeSubdomains,
        }
        
        if self.search:
            params["search"] = self.search
        
        # Ensure API key is stripped of any whitespace
        cleaned_api_key = self.api_key.strip() if self.api_key else ""
        
        app = FirecrawlApp(api_key=cleaned_api_key)
        results = app.map_url(self.url, params=params)
        return Data(data=results) 