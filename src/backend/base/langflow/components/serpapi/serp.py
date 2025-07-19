from typing import Any

from langchain_community.utilities.serpapi import SerpAPIWrapper
from langchain_core.tools import ToolException
from lfx.custom.custom_component.component import Component
from loguru import logger
from pydantic import BaseModel, Field

from langflow.inputs.inputs import DictInput, IntInput, MultilineInput, SecretStrInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


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


class SerpComponent(Component):
    display_name = "Serp Search API"
    description = "Call Serp Search API with result limiting"
    name = "Serp"
    icon = "SerpSearch"

    inputs = [
        SecretStrInput(name="serpapi_api_key", display_name="SerpAPI API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        DictInput(name="search_params", display_name="Parameters", advanced=True, is_list=True),
        IntInput(name="max_results", display_name="Max Results", value=5, advanced=True),
        IntInput(name="max_snippet_length", display_name="Max Snippet Length", value=100, advanced=True),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
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

    def run_model(self) -> list[Data]:
        return self.fetch_content()

    def fetch_content(self) -> list[Data]:
        wrapper = self._build_wrapper(self.search_params)

        def search_func(
            query: str, params: dict[str, Any] | None = None, max_results: int = 5, max_snippet_length: int = 100
        ) -> list[Data]:
            try:
                local_wrapper = wrapper
                if params:
                    local_wrapper = self._build_wrapper(params)

                full_results = local_wrapper.results(query)
                organic_results = full_results.get("organic_results", [])[:max_results]

                limited_results = [
                    Data(
                        text=result.get("snippet", ""),
                        data={
                            "title": result.get("title", "")[:max_snippet_length],
                            "link": result.get("link", ""),
                            "snippet": result.get("snippet", "")[:max_snippet_length],
                        },
                    )
                    for result in organic_results
                ]

            except Exception as e:
                error_message = f"Error in SerpAPI search: {e!s}"
                logger.debug(error_message)
                raise ToolException(error_message) from e
            return limited_results

        results = search_func(
            self.input_value,
            params=self.search_params,
            max_results=self.max_results,
            max_snippet_length=self.max_snippet_length,
        )
        self.status = results
        return results

    def fetch_content_text(self) -> Message:
        data = self.fetch_content()
        result_string = ""
        for item in data:
            result_string += item.text + "\n"
        self.status = result_string
        return Message(text=result_string)
