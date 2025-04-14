from spider.spider import Spider

from langflow.base.langchain_utilities.spider_constants import MODES
from langflow.custom.custom_component.component import Component
from langflow.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema.data import Data


class SpiderTool(Component):
    display_name: str = "Spider Web Crawler & Scraper"
    description: str = "Spider API for web crawling and scraping."
    output_types: list[str] = ["Document"]
    documentation: str = "https://spider.cloud/docs/api"

    inputs = [
        SecretStrInput(
            name="spider_api_key",
            display_name="Spider API Key",
            required=True,
            password=True,
            info="The Spider API Key, get it from https://spider.cloud",
        ),
        StrInput(
            name="url",
            display_name="URL",
            required=True,
            info="The URL to scrape or crawl",
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            required=True,
            options=MODES,
            value=MODES[0],
            info="The mode of operation: scrape or crawl",
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            info="The maximum amount of pages allowed to crawl per website. Set to 0 to crawl all pages.",
            advanced=True,
        ),
        IntInput(
            name="depth",
            display_name="Depth",
            info="The crawl limit for maximum depth. If 0, no limit will be applied.",
            advanced=True,
        ),
        StrInput(
            name="blacklist",
            display_name="Blacklist",
            info="Blacklist paths that you do not want to crawl. Use Regex patterns.",
            advanced=True,
        ),
        StrInput(
            name="whitelist",
            display_name="Whitelist",
            info="Whitelist paths that you want to crawl, ignoring all other routes. Use Regex patterns.",
            advanced=True,
        ),
        BoolInput(
            name="readability",
            display_name="Use Readability",
            info="Use readability to pre-process the content for reading.",
            advanced=True,
        ),
        IntInput(
            name="request_timeout",
            display_name="Request Timeout",
            info="Timeout for the request in seconds.",
            advanced=True,
        ),
        BoolInput(
            name="metadata",
            display_name="Metadata",
            info="Include metadata in the response.",
            advanced=True,
        ),
        DictInput(
            name="params",
            display_name="Additional Parameters",
            info="Additional parameters to pass to the API. If provided, other inputs will be ignored.",
        ),
    ]

    outputs = [
        Output(display_name="Markdown", name="content", method="crawl"),
    ]

    def crawl(self) -> list[Data]:
        if self.params:
            parameters = self.params["data"]
        else:
            parameters = {
                "limit": self.limit or None,
                "depth": self.depth or None,
                "blacklist": self.blacklist or None,
                "whitelist": self.whitelist or None,
                "readability": self.readability,
                "request_timeout": self.request_timeout or None,
                "metadata": self.metadata,
                "return_format": "markdown",
            }

        app = Spider(api_key=self.spider_api_key)
        if self.mode == "scrape":
            parameters["limit"] = 1
            result = app.scrape_url(self.url, parameters)
        elif self.mode == "crawl":
            result = app.crawl_url(self.url, parameters)
        else:
            msg = f"Invalid mode: {self.mode}. Must be 'scrape' or 'crawl'."
            raise ValueError(msg)

        records = []

        for record in result:
            if self.metadata:
                records.append(
                    Data(
                        data={
                            "content": record["content"],
                            "url": record["url"],
                            "metadata": record["metadata"],
                        }
                    )
                )
            else:
                records.append(Data(data={"content": record["content"], "url": record["url"]}))
        return records


class SpiderToolError(Exception):
    """SpiderTool error."""
