from typing import List, Union
from langflow import CustomComponent

from metaphor_python import Metaphor  # type: ignore
from langchain.tools import Tool
from langchain.agents import tool
from langchain.agents.agent_toolkits.base import BaseToolkit


class MetaphorToolkit(CustomComponent):
    display_name: str = "Metaphor"
    description: str = "Metaphor Toolkit"
    documentation = (
        "https://python.langchain.com/docs/integrations/tools/metaphor_search"
    )
    beta = True
    # api key should be password = True
    field_config = {
        "metaphor_api_key": {"display_name": "Metaphor API Key", "password": True},
        "code": {"advanced": True},
    }

    def build(
        self,
        metaphor_api_key: str,
        use_autoprompt: bool = True,
        search_num_results: int = 5,
        similar_num_results: int = 5,
    ) -> Union[Tool, BaseToolkit]:
        # If documents, then we need to create a Vectara instance using .from_documents
        client = Metaphor(api_key=metaphor_api_key)

        @tool
        def search(query: str):
            """Call search engine with a query."""
            return client.search(
                query, use_autoprompt=use_autoprompt, num_results=search_num_results
            )

        @tool
        def get_contents(ids: List[str]):
            """Get contents of a webpage.

            The ids passed in should be a list of ids as fetched from `search`.
            """
            return client.get_contents(ids)

        @tool
        def find_similar(url: str):
            """Get search results similar to a given URL.

            The url passed in should be a URL returned from `search`
            """
            return client.find_similar(url, num_results=similar_num_results)

        return [search, get_contents, find_similar]  # type: ignore
