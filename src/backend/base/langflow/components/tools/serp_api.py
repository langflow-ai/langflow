from typing import Any

from langchain.tools import StructuredTool
from langchain_community.utilities.serpapi import SerpAPIWrapper
from langchain_core.tools import ToolException
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import DictInput, IntInput, MultilineInput, SecretStrInput
from langflow.schema import Data


class SerpAPISchema(BaseModel):
    """Schema for SerpAPI search parameters."""

    query: str = Field(..., description="The search query")
    params: dict[str, Any] | None = Field(
        default={
            "engine": "google",
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en",
        },
        description="Additional search parameters",
    )
    max_results: int = Field(5, description="Maximum number of results to return")
    max_snippet_length: int = Field(100, description="Maximum length of each result snippet")


class SerpAPIComponent(LCToolComponent):
    display_name = "Serp Search API [DEPRECATED]"
    description = "Call Serp Search API with result limiting"
    name = "SerpAPI"
    icon = "SerpSearch"
    legacy = True

    inputs = [
        SecretStrInput(name="serpapi_api_key", display_name="SerpAPI API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
        ),
        DictInput(name="search_params", display_name="Parameters", advanced=True, is_list=True),
        IntInput(name="max_results", display_name="Max Results", value=5, advanced=True),
        IntInput(name="max_snippet_length", display_name="Max Snippet Length", value=100, advanced=True),
    ]

    def _build_wrapper(self, params: dict[str, Any] | None = None) -> SerpAPIWrapper:
        """Build a SerpAPIWrapper with the provided parameters."""
        params = params or {}
        if params:
            return SerpAPIWrapper(
                serpapi_api_key=self.serpapi_api_key,
                params=params,
            )
        return SerpAPIWrapper(serpapi_api_key=self.serpapi_api_key)

    def build_tool(self) -> Tool:
        wrapper = self._build_wrapper(self.search_params)

        def search_func(
            query: str, params: dict[str, Any] | None = None, max_results: int = 5, max_snippet_length: int = 100
        ) -> list[dict[str, Any]]:
            try:
                local_wrapper = wrapper
                if params:
                    local_wrapper = self._build_wrapper(params)

                full_results = local_wrapper.results(query)
                organic_results = full_results.get("organic_results", [])[:max_results]

                limited_results = []
                for result in organic_results:
                    limited_result = {
                        "title": result.get("title", "")[:max_snippet_length],
                        "link": result.get("link", ""),
                        "snippet": result.get("snippet", "")[:max_snippet_length],
                    }
                    limited_results.append(limited_result)

            except Exception as e:
                error_message = f"Error in SerpAPI search: {e!s}"
                logger.debug(error_message)
                raise ToolException(error_message) from e
            return limited_results

        tool = StructuredTool.from_function(
            name="serp_search_api",
            description="Search for recent results using SerpAPI with result limiting",
            func=search_func,
            args_schema=SerpAPISchema,
        )

        self.status = "SerpAPI Tool created"
        return tool

    def run_model(self) -> list[Data]:
        tool = self.build_tool()
        try:
            results = tool.run(
                {
                    "query": self.input_value,
                    "params": self.search_params or {},
                    "max_results": self.max_results,
                    "max_snippet_length": self.max_snippet_length,
                }
            )

            data_list = [Data(data=result, text=result.get("snippet", "")) for result in results]

        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error running SerpAPI")
            self.status = f"Error: {e}"
            return [Data(data={"error": str(e)}, text=str(e))]

        self.status = data_list  # type: ignore[assignment]
        return data_list
