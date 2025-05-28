from langchain_core.tools import tool
from metaphor_python import Metaphor

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import BoolInput, IntInput, Output, SecretStrInput


class ExaSearchToolkit(Component):
    display_name = "Exa Search"
    description = "Exa Search toolkit for search and content retrieval"
    documentation = "https://python.langchain.com/docs/integrations/tools/metaphor_search"
    beta = True
    name = "ExaSearch"
    icon = "ExaSearch"

    inputs = [
        SecretStrInput(
            name="metaphor_api_key",
            display_name="Exa Search API Key",
            password=True,
        ),
        BoolInput(
            name="use_autoprompt",
            display_name="Use Autoprompt",
            value=True,
        ),
        IntInput(
            name="search_num_results",
            display_name="Search Number of Results",
            value=5,
        ),
        IntInput(
            name="similar_num_results",
            display_name="Similar Number of Results",
            value=5,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def build_toolkit(self) -> Tool:
        client = Metaphor(api_key=self.metaphor_api_key)

        @tool
        def search(query: str):
            """Call search engine with a query."""
            return client.search(query, use_autoprompt=self.use_autoprompt, num_results=self.search_num_results)

        @tool
        def get_contents(ids: list[str]):
            """Get contents of a webpage.

            The ids passed in should be a list of ids as fetched from `search`.
            """
            return client.get_contents(ids)

        @tool
        def find_similar(url: str):
            """Get search results similar to a given URL.

            The url passed in should be a URL returned from `search`
            """
            return client.find_similar(url, num_results=self.similar_num_results)

        return [search, get_contents, find_similar]
