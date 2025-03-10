import json

from requests import HTTPError

from langflow.custom  import Component
from langflow.io import (
    BoolInput,
    DataInput,
    IntInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data

# Define HTTP status code constants
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404


class WaterCrawlError(Exception):
    """Exception raised for WaterCrawl API errors."""


class WaterCrawlScrapeApi(Component):
    display_name: str = "WaterCrawlScrapeApi"
    description: str = "Scrape a URL using WaterCrawl API."
    documentation: str = "https://watercrawl.dev/docs"
    field_order: list[str] = ["api_key", "url", "wait_time", "only_main_content"]
    icon: str = "WaterCrawlCrawlApi"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            info="Your WaterCrawl API key.",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="URL to scrape.",
        ),
        IntInput(
            name="wait_time",
            display_name="Wait Time",
            info="Wait time in milliseconds for the page to load.",
        ),
        BoolInput(
            name="only_main_content",
            display_name="Only Main Content",
            info="Whether to extract only the main content of the page.",
        ),
        BoolInput(
            name="include_html",
            display_name="Include HTML",
            info="Whether to include HTML in the response.",
            show=False,
        ),
        BoolInput(
            name="include_links",
            display_name="Include Links",
            info="Whether to include links in the response.",
            show=False,
        ),
        StrInput(
            name="exclude_tags",
            display_name="Exclude Tags",
            info="Comma-separated HTML tags to exclude from the scrape (e.g., 'nav,footer,aside').",
            show=False,
        ),
        StrInput(
            name="include_tags",
            display_name="Include Tags",
            info="Comma-separated HTML tags to specifically include in the scrape (e.g., 'article,main').",
            show=False,
        ),
        DataInput(
            name="page_options",
            display_name="Page Options",
            info="Options for how to scrape individual pages.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="scrape"),
    ]

    def scrape(self) -> Data:
        try:
            from watercrawl import WaterCrawlAPIClient
        except ImportError as e:
            error_msg = "Please install watercrawl-py: pip install watercrawl-py"
            raise ImportError(error_msg) from e

        # Prepare page options
        page_options = self.page_options.__dict__["data"] if self.page_options else {}

        # Add specific parameters if provided
        if self.wait_time is not None:
            page_options["wait_time"] = self.wait_time or 1500
        if self.include_html is not None:
            page_options["include_html"] = self.include_html
        if self.only_main_content is not None:
            page_options["only_main_content"] = self.only_main_content
        if self.include_links is not None:
            page_options["include_links"] = self.include_links
        if self.exclude_tags:
            # Convert comma-separated string to list
            page_options["exclude_tags"] = [tag.strip() for tag in self.exclude_tags.split(",")]
        if self.include_tags:
            # Convert comma-separated string to list
            page_options["include_tags"] = [tag.strip() for tag in self.include_tags.split(",")]

        # Initialize the client and scrape the URL
        client = WaterCrawlAPIClient(self.api_key)

        url = self.url
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        try:
            scrape_result = client.scrape_url(url, page_options=page_options)
        except HTTPError as e:
            if e.response.status_code == HTTP_BAD_REQUEST:
                errors = e.response.json()["errors"]
                error_message = f"Failed to scrape URL: {json.dumps(errors)}"
                raise WaterCrawlError(error_message) from e
            if e.response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN, HTTP_NOT_FOUND):
                error_message = e.response.json()['message']
                raise WaterCrawlError(error_message) from e

            raise

        return Data(data=scrape_result)
