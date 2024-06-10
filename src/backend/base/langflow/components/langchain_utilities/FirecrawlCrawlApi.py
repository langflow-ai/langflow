from typing import Optional
from firecrawl.firecrawl import FirecrawlApp
from langflow.custom import CustomComponent
from langflow.schema.schema import Record
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
import json
import uuid


class FirecrawlCrawlApi(CustomComponent):
    display_name: str = "FirecrawlCrawlApi"
    description: str = "Firecrawl Crawl API."
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
        crawlerOptions: Optional[JsonToolkit] = None,
        pageOptions: Optional[JsonToolkit] = None,
        idempotency_key: Optional[str] = None,
    ) -> Record:
        if crawlerOptions:
            crawler_options_dict = crawlerOptions.spec.dict_
        else:
            crawler_options_dict = {}

        if pageOptions:
            page_options_dict = pageOptions.spec.dict_
        else:
            page_options_dict = {}

        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        app = FirecrawlApp(api_key=api_key)
        crawl_result = app.crawl_url(
            url,
            {
                "crawlerOptions": json.loads(json.dumps(crawler_options_dict)),
                "pageOptions": json.loads(json.dumps(page_options_dict)),
            },
            True,
            2,
            idempotency_key,
        )

        records = [Record(data=item) for item in crawl_result]

        return records
