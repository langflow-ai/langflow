from typing import Optional
from firecrawl.firecrawl import FirecrawlApp
from langflow.custom import CustomComponent
from langflow.schema import Data

class FirecrawlScrapeApi(CustomComponent):
    display_name: str = "FirecrawlScrapeApi"
    description: str = "Firecrawl Scrape API."
    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/scrape"
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
            "info": "The URL to scrape.",
        },
        "timeout": {
            "display_name": "Timeout",
            "info": "Timeout in milliseconds for the request.",
            "field_type": "int",
            "default_value": 10000,
        },
        "pageOptions": {
            "display_name": "Page Options",
            "info": "The page options to send with the request.",
        },
        "extractorOptions": {
            "display_name": "Extractor Options",
            "info": "The extractor options to send with the request.",
        },
    }

    def build(
        self,
        api_key: str,
        url: str,
        timeout: Optional[int] = 10000,
        pageOptions: Optional[Data] = None,
        extractorOptions: Optional[Data] = None,
    ) -> Data:
        if extractorOptions:
            extractor_options_dict = extractorOptions.__dict__['data']['text']
        else:
            extractor_options_dict = {}

        if pageOptions:
            page_options_dict = pageOptions.__dict__['data']['text']
        else:
            page_options_dict = {}

        app = FirecrawlApp(api_key=api_key)
        results = app.scrape_url(
            url,
            {
                "timeout": str(timeout),
                "extractorOptions": extractor_options_dict,
                "pageOptions": page_options_dict,
            },
        )

        record = Data(data=results)
        return record
