from typing import Optional, List
from firecrawl.firecrawl import FirecrawlApp
from langflow.custom import CustomComponent
from langflow.schema.schema import Record
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
import json


class FirecrawlSearchApi(CustomComponent):
    display_name: str = "FirecrawlSearchApi"
    description: str = "Firecrawl Search API."
    output_types: list[str] = ["Document"]
    documentation: str = "https://docs.firecrawl.dev/api-reference/endpoint/search"
    field_config = {
        "api_key": {
            "display_name": "API Key",
            "field_type": "str",
            "required": True,
            "password": True,
            "info": "The API key to use Firecrawl API.",
        },
        "query": {
            "display_name": "Query",
            "field_type": "str",
            "required": True,
            "info": "The query string to search for.",
        },
        "searchOptions": {
            "display_name": "Search Options",
            "info": "Options to refine search results.",
        },
        "pageOptions": {
            "display_name": "Page Options",
            "info": "Options to control the page content returned.",
        },
    }

    def build(
        self,
        api_key: str,
        query: str,
        searchOptions: Optional[JsonToolkit] = None,
        pageOptions: Optional[JsonToolkit] = None,
    ) -> List[Record]:
        if searchOptions:
            search_options_dict = searchOptions.spec.dict_
        else:
            search_options_dict = {}

        if pageOptions:
            page_options_dict = pageOptions.spec.dict_
        else:
            page_options_dict = {}

        app = FirecrawlApp(api_key=api_key)
        search_result = app.search(
            query,
            {
                "searchOptions": json.loads(json.dumps(search_options_dict)),
                "pageOptions": json.loads(json.dumps(page_options_dict)),
            },
        )

        records = [Record(data=item) for item in search_result]

        return records
