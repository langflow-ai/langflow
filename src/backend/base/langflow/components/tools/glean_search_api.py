import json
from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel
from pydantic.v1 import Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import IntInput, MultilineInput, NestedDictInput, SecretStrInput, StrInput
from langflow.io import Output
from langflow.schema import Data, DataFrame


class GleanSearchAPISchema(BaseModel):
    query: str = Field(..., description="The search query")
    page_size: int = Field(10, description="Maximum number of results to return")
    request_options: dict[str, Any] | None = Field(default_factory=dict, description="Request Options")


class GleanAPIWrapper(BaseModel):
    """Wrapper around Glean API."""

    glean_api_url: str
    glean_access_token: str
    act_as: str = "langflow-component@datastax.com"  # TODO: Detect this

    def _prepare_request(
        self,
        query: str,
        page_size: int = 10,
        request_options: dict[str, Any] | None = None,
    ) -> dict:
        # Ensure there's a trailing slash
        url = self.glean_api_url
        if not url.endswith("/"):
            url += "/"

        return {
            "url": urljoin(url, "search"),
            "headers": {
                "Authorization": f"Bearer {self.glean_access_token}",
                "X-Scio-ActAs": self.act_as,
            },
            "payload": {
                "query": query,
                "pageSize": page_size,
                "requestOptions": request_options,
            },
        }

    def results(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        results = self._search_api_results(query, **kwargs)

        if len(results) == 0:
            msg = "No good Glean Search Result was found"
            raise AssertionError(msg)

        return results

    def run(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        try:
            results = self.results(query, **kwargs)

            processed_results = []
            for result in results:
                if "title" in result:
                    result["snippets"] = result.get("snippets", [{"snippet": {"text": result["title"]}}])
                    if "text" not in result["snippets"][0]:
                        result["snippets"][0]["text"] = result["title"]

                processed_results.append(result)
        except Exception as e:
            error_message = f"Error in Glean Search API: {e!s}"
            raise ToolException(error_message) from e

        return processed_results

    def _search_api_results(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        request_details = self._prepare_request(query, **kwargs)

        response = httpx.post(
            request_details["url"],
            json=request_details["payload"],
            headers=request_details["headers"],
        )

        response.raise_for_status()
        response_json = response.json()

        return response_json.get("results", [])

    @staticmethod
    def _result_as_string(result: dict) -> str:
        return json.dumps(result, indent=4)


class GleanSearchAPIComponent(LCToolComponent):
    display_name: str = "Glean Search API"
    description: str = "Search using Glean's API."
    documentation: str = "https://docs.langflow.org/Components/components-tools#glean-search-api"
    icon: str = "Glean"

    outputs = [
        Output(display_name="Data", name="data", method="run_model"),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    inputs = [
        StrInput(name="glean_api_url", display_name="Glean API URL", required=True),
        SecretStrInput(name="glean_access_token", display_name="Glean Access Token", required=True),
        MultilineInput(name="query", display_name="Query", required=True, tool_mode=True),
        IntInput(name="page_size", display_name="Page Size", value=10),
        NestedDictInput(name="request_options", display_name="Request Options", required=False),
    ]

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper(
            glean_api_url=self.glean_api_url,
            glean_access_token=self.glean_access_token,
        )

        tool = StructuredTool.from_function(
            name="glean_search_api",
            description="Search Glean for relevant results.",
            func=wrapper.run,
            args_schema=GleanSearchAPISchema,
        )

        self.status = "Glean Search API Tool for Langchain"

        return tool

    def run_model(self) -> list[Data]:
        tool = self.build_tool()

        results = tool.run(
            {
                "query": self.query,
                "page_size": self.page_size,
                "request_options": self.request_options,
            }
        )

        # Build the data
        data = [Data(data=result, text=result["snippets"][0]["text"]) for result in results]
        self.status = data  # type: ignore[assignment]

        return data

    def _build_wrapper(
        self,
        glean_api_url: str,
        glean_access_token: str,
    ):
        return GleanAPIWrapper(
            glean_api_url=glean_api_url,
            glean_access_token=glean_access_token,
        )

    def as_dataframe(self) -> DataFrame:
        """Convert the Glean search results to a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the search results.
        """
        data = self.run_model()
        if isinstance(data, list):
            return DataFrame(data=[d.data for d in data])
        return DataFrame(data=[data.data])
