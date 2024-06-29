from typing import Optional
from spider.spider import Spider
from langflow.custom import CustomComponent
from langflow.schema import Data
from langflow.base.langchain_utilities.spider_constants import MODES
from langflow.inputs import (
    SecretStrInput,
    StrInput,
    DropdownInput,
    IntInput,
    BoolInput,
    DictInput
)
import uuid


print(dir(Spider))

class SpiderTool(CustomComponent):
    display_name: str = "Spider Web Crawler & Scraper"
    description: str = "Spider API."
    output_types: list[str] = ["Document"]
    documentation: str = "https://spider.cloud/docs/api"
    icon: str = "Spider"

    inputs = [
        SecretStrInput(
            name="spider_api_key",
            display_name="Spider API Key",
            info="The Spider API Key",
            advanced=False,
            value="SPIDER_API_KEY",
            required=True,
        ),
        StrInput(
            name="url",
            display_name="URL",
            advanced=False,
            info="The URL to scrape or crawl",
        ),
        DropdownInput(
            name="mode", display_name="Mode", advanced=False, options=MODES, value=MODES[0]
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            info="The maximum amount of pages allowed to crawl per website. Remove the value or set it to 0 to crawl all pages.",
        ),
        IntInput(
            name="depth",
            display_name="Depth",
            advanced=True,
            info="The crawl limit for maximum depth. If 0, no limit will be applied.",
        ),
        StrInput(
            name="blacklist",
            display_name="Blacklist",
            advanced=True,
            info="Blacklist a set of paths that you do not want to crawl. You can use Regex patterns to help with the list. For example: /login, /blog/*",
        ),
        StrInput(
            name="whitelist",
            display_name="Whitelist",
            advanced=True,
            info="Whitelist a set of paths that you want to crawl, ignoring all other routes that do not match the patterns. You can use regex patterns to help with the list. For example: /blog/*",
        ),
        BoolInput(
            name="use_readability",
            display_name="Use Readability",
            advanced=True,
            info="Use readability to pre-process the content for reading. This may drastically improve the content for LLM usage.",
        ),
        IntInput(
            name="request_timeout",
            display_name="Request Timeout",
            advanced=True,
            info="Include OpenAI embeddings for title and description. The default is false.",
        ),
        BoolInput(
            name="return_embeddings",
            display_name="Return Embeddings",
            advanced=True,
            info="Return embeddings",
        ),
        DictInput(
            name="params",
            display_name="Params",
            advanced=True,
            info="Additional parameters to pass to the API. If provided, the other inputs will be ignored. You can see the full list of parameters in the Spider documentation.",
        )
    ]

    def build(
        self,
        api_key: str,
        url: str,
        mode: str,
        limit: Optional[int] = 0,
        depth: Optional[int] = 0,
        blacklist: Optional[str] = None,
        whitelist: Optional[str] = None,
        use_readability: Optional[bool] = False,
        request_timeout: Optional[int] = 30,
        return_embeddings: Optional[bool] = False,
        params: Optional[Data] = None,
    ) -> Data:
        if params:
            parameters = params.data
        else:
            parameters = {
                "limit": limit,
                "depth": depth,
                "blacklist": blacklist,
                "whitelist": whitelist,
                "use_readability": use_readability,
                "request_timeout": request_timeout,
                "return_embeddings": return_embeddings,
                "return_format": "markdown",
            }

        app = Spider(api_key=api_key)
        try:
            if mode == "scrape":
                crawl_result = app.scrape_url(url, parameters)
            elif mode == "crawl":
                crawl_result = app.crawl_url(url, parameters)
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
        records = Data(data={"results": crawl_result})
        return records
