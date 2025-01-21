from typing import Any

from langchain_community.utilities.searchapi import SearchApiAPIWrapper

from langflow.custom import Component
from langflow.inputs import DictInput, DropdownInput, IntInput, MultilineInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data
from langflow.schema.message import Message


class SearchComponent(Component):
    display_name: str = "Search API"
    description: str = "Call the searchapi.io API with result limiting"
    documentation: str = "https://www.searchapi.io/docs/google"
    icon = "SearchAPI"

    inputs = [
        DropdownInput(name="engine", display_name="Engine", value="google", options=["google", "bing", "duckduckgo"]),
        SecretStrInput(name="api_key", display_name="SearchAPI API Key", required=True),
        MultilineInput(
            name="input_value",
            display_name="Input",
            tool_mode=True,
        ),
        DictInput(name="search_params", display_name="Search parameters", advanced=True, is_list=True),
        IntInput(name="max_results", display_name="Max Results", value=5, advanced=True),
        IntInput(name="max_snippet_length", display_name="Max Snippet Length", value=100, advanced=True),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Text", name="text", method="fetch_content_text"),
    ]

    def _build_wrapper(self):
        return SearchApiAPIWrapper(engine=self.engine, searchapi_api_key=self.api_key)

    def run_model(self) -> list[Data]:
        return self.fetch_content()

    def fetch_content(self) -> list[Data]:
        wrapper = self._build_wrapper()

        def search_func(
            query: str, params: dict[str, Any] | None = None, max_results: int = 5, max_snippet_length: int = 100
        ) -> list[Data]:
            params = params or {}
            full_results = wrapper.results(query=query, **params)
            organic_results = full_results.get("organic_results", [])[:max_results]

            return [
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

        results = search_func(
            self.input_value,
            self.search_params or {},
            self.max_results,
            self.max_snippet_length,
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
