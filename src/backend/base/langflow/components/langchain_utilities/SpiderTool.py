from typing import Optional
from spider.spider import Spider
from langflow.custom import Component
from langflow.schema import Data
from langflow.base.langchain_utilities.spider_constants import MODES
from langflow.inputs import (
    SecretStrInput,
    StrInput,
    DropdownInput,
    IntInput,
    BoolInput,
    DictInput,
)


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
            name="use_readability",
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

    def build(
        self,
        spider_api_key: str,
        url: str,
        mode: str,
        limit: Optional[int] = 0,
        depth: Optional[int] = 0,
        blacklist: Optional[str] = None,
        whitelist: Optional[str] = None,
        use_readability: Optional[bool] = False,
        request_timeout: Optional[int] = 30,
        metadata: Optional[bool] = False,
        params: Optional[Data] = None,
    ) -> Data:
        if params:
            parameters = params.__dict__["data"]
        else:
            parameters = {
                "limit": limit,
                "depth": depth,
                "blacklist": blacklist,
                "whitelist": whitelist,
                "use_readability": use_readability,
                "request_timeout": request_timeout,
                "metadata": metadata,
                "return_format": "markdown",
            }

        app = Spider(api_key=spider_api_key)
        try:
            if mode == "scrape":
                parameters["limit"] = 1
                result = app.scrape_url(url, parameters)
            elif mode == "crawl":
                result = app.crawl_url(url, parameters)
            else:
                raise ValueError(f"Invalid mode: {mode}. Must be 'scrape' or 'crawl'.")
        except Exception as e:
            raise Exception(f"Error: {str(e)}")

        records = []

        for record in result:
            records.append(Data(data={"content": record["content"], "url": record["url"]}))
        return records
