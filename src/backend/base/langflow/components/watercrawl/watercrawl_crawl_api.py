import json

from requests import HTTPError

from langflow.custom import Component
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


class WaterCrawlCrawlApi(Component):
    display_name: str = "WaterCrawlCrawlApi"
    description: str = "Crawl a website using WaterCrawl API."
    documentation: str = "https://watercrawl.dev/docs"
    field_order: list[str] = ["api_key", "url", "max_depth", "page_limit", "wait_for_completion"]
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
            info="URL to crawl.",
        ),
        IntInput(
            name="max_depth",
            display_name="Max Depth",
            info="Maximum depth for crawling (e.g., 2). Defaults to 1 if not provided.",
        ),
        IntInput(
            name="page_limit",
            display_name="Page Limit",
            info="Maximum number of pages to crawl (e.g., 100). Defaults to 10 if not provided.",
        ),
        StrInput(
            name="allowed_domains",
            display_name="Allowed Domains",
            info="Comma-separated list of domains allowed to crawl (e.g., 'example.com,test.com').",
            show=False,
        ),
        StrInput(
            name="exclude_paths",
            display_name="Exclude Paths",
            info="Comma-separated paths to exclude from crawling (e.g., '/private/*,/admin/*').",
            show=False,
        ),
        StrInput(
            name="include_paths",
            display_name="Include Paths",
            info="Comma-separated paths to specifically include in crawling (e.g., '/blog/*,/products/*').",
            show=False,
        ),
        BoolInput(
            name="wait_for_completion",
            display_name="Wait For Completion",
            info="Whether to wait for the crawl to complete before returning. Defaults to True.",
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
            name="spider_options",
            display_name="Spider Options",
            info="Options for configuring the crawler.",
        ),
        DataInput(
            name="page_options",
            display_name="Page Options",
            info="Options for how to scrape individual pages.",
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="crawl"),
    ]

    def crawl(self) -> Data:
        try:
            from watercrawl import WaterCrawlAPIClient
        except ImportError as e:
            error_msg = "Please install watercrawl-py: pip install watercrawl-py"
            raise ImportError(error_msg) from e

        # Prepare spider options
        spider_options = self.spider_options.__dict__["data"] if self.spider_options else {}

        # Add specific parameters if provided
        if self.max_depth is not None:
            spider_options["max_depth"] = self.max_depth
        if self.page_limit is not None:
            spider_options["page_limit"] = self.page_limit
        if self.allowed_domains:
            # Convert comma-separated string to list
            spider_options["allowed_domains"] = [domain.strip() for domain in self.allowed_domains.split(",")]
        if self.exclude_paths:
            # Convert comma-separated string to list
            spider_options["exclude_paths"] = [path.strip() for path in self.exclude_paths.split(",")]
        if self.include_paths:
            # Convert comma-separated string to list
            spider_options["include_paths"] = [path.strip() for path in self.include_paths.split(",")]

        # Set reasonable defaults if not provided
        if "max_depth" not in spider_options or not spider_options["max_depth"]:
            spider_options["max_depth"] = 1
        if "page_limit" not in spider_options or not spider_options["page_limit"]:
            spider_options["page_limit"] = 10

        # Get page options
        page_options = self.page_options.__dict__["data"] if self.page_options else {}

        # Add specific parameters if provided for page options
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

        # Initialize the client
        client = WaterCrawlAPIClient(self.api_key)

        url = self.url
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        # Start crawl
        try:
            crawl_result = client.create_crawl_request(
                url=url, spider_options=spider_options, page_options=page_options
            )
        except HTTPError as e:
            if e.response.status_code == HTTP_BAD_REQUEST:
                errors = e.response.json()["errors"]
                error_message = f"Failed to scrape URL: {json.dumps(errors)}"
                raise WaterCrawlError(error_message) from e
            if e.response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN, HTTP_NOT_FOUND):
                error_message = e.response.json()['message']
                raise WaterCrawlError(error_message) from e
            raise

        # If wait_for_completion is True, monitor the crawl until it's complete
        if self.wait_for_completion:
            crawl_id = crawl_result["uuid"]
            results = []
            # Monitor the crawl until it's complete
            for event in client.monitor_crawl_request(crawl_id, download=True):
                if event["type"] == "result":
                    results.append(event["data"])
                elif event["type"] == "state":
                    crawl_result = event["data"]

            return Data(data={"crawl_info": crawl_result, "results": results})

        return Data(data={"crawl_info": crawl_result, "results": []})
