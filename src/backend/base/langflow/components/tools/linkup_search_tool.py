import httpx
from langchain.tools import StructuredTool
from langchain_core.tools import ToolException
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DropdownInput, MessageTextInput
from langflow.io import Output, SecretStrInput
from langflow.schema import Data


class LinkupSearchToolComponent(LCToolComponent):
    display_name = "Linkup Search Tool"
    description = """**Linkup Search Tool** is a search engine that performs web search queries using
    the Linkup API, which includes results from both public and premium web sources. It supports two
    modes of search depth - standard and deep - allowing for flexible information retrieval depending
    on the complexity of the query."""
    icon = "LinkupIcon"
    name = "LinkupSearch"
    documentation = "https://docs.linkup.so/"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Linkup API Key",
            required=True,
            info="Your Linkup API Key.",
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The search query you want to execute with Linkup.",
        ),
        DropdownInput(
            name="depth",
            display_name="Search Depth",
            info="""The search depth to perform. Use 'standard' for straightforward queries with likely direct answers.
            Use 'deep' for complex queries requiring comprehensive analysis.""",
            options=["standard", "deep"],
            value="standard",
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_toolkit"),
    ]

    def build_toolkit(self) -> Tool:
        """Build the Linkup search toolkit."""
        return StructuredTool.from_function(
            name="linkup_search",
            description="Perform a web search using the Linkup API.",
            func=self._linkup_search,
        )

    def _linkup_search(self, query: str) -> list[Data]:
        """Execute a search using the Linkup API."""
        if not query:
            msg = "Query cannot be empty"
            raise ValueError(msg)

        try:
            response = httpx.post(
                "https://api.linkup.so/v1/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "q": query,
                    "outputType": "searchResults",
                    "includeImages": True,
                    "depth": self.depth,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("results"):
                self.status = "No results found"
                return []

            data_results = [
                Data(
                    type="text",
                    name=result.get("name", "Untitled"),
                    url=result.get("url", ""),
                    content=result.get("content", ""),
                    data=result,
                )
                for result in data["results"]
            ]

            self.status = data_results
        except httpx.TimeoutException as e:
            error_msg = f"Request timed out: {e!s}"
            self.status = error_msg
            raise ToolException(error_msg) from e
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error: {e.response.status_code} - {e.response.text}"
            logger.debug(error_message)
            self.status = error_message
            raise ToolException(error_message) from e
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            logger.opt(exception=True).debug("Error running Linkup Search")
            self.status = error_message
            raise ToolException(error_message) from e
        else:
            return data_results
