import uuid
from typing import Optional

from langflow.custom import CustomComponent
from langflow.schema import Data


class FirecrawlCrawlApi(CustomComponent):
    display_name: str = "FirecrawlCrawlApi"
    description: str = "Firecrawl Crawl API."
    name = "FirecrawlCrawlApi"

    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/crawl"
    field_config = {
        "api_key": {
            "display_name": "API Key",
            "field_type": "str",
            "required": True,
            "password": True,
            "info": "The API key to use Firecrawl API.",
        },
        "url": {
            "display_name": "URL",
            "field_type": "str",
            "required": True,
            "info": "The base URL to start crawling from.",
        },
        "timeout": {
            "display_name": "Timeout",
            "field_type": "int",
            "info": "The timeout in milliseconds.",
        },
        "crawlerOptions": {
            "display_name": "Crawler Options",
            "info": "Options for the crawler behavior.",
        },
        "pageOptions": {
            "display_name": "Page Options",
            "info": "The page options to send with the request.",
        },
        "idempotency_key": {
            "display_name": "Idempotency Key",
            "field_type": "str",
            "info": "Optional idempotency key to ensure unique requests.",
        },
    }

    def build(
        self,
        api_key: str,
        url: str,
        timeout: int = 30000,
        crawlerOptions: Optional[Data] = None,
        pageOptions: Optional[Data] = None,
        idempotency_key: Optional[str] = None,
    ) -> Data:
        try:
            from firecrawl.firecrawl import FirecrawlApp  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import firecrawl integration package. " "Please install it with `pip install firecrawl-py`."
            )
        if crawlerOptions:
            crawler_options_dict = crawlerOptions.__dict__["data"]["text"]
        else:
            crawler_options_dict = {}

        if pageOptions:
            page_options_dict = pageOptions.__dict__["data"]["text"]
        else:
            page_options_dict = {}

        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        app = FirecrawlApp(api_key=api_key)
        crawl_result = app.crawl_url(
            url,
            {
                "crawlerOptions": crawler_options_dict,
                "pageOptions": page_options_dict,
            },
            True,
            int(timeout / 1000),
            idempotency_key,
        )

        records = Data(data={"results": crawl_result})
        return records
