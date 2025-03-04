from typing import Any

from langchain.tools import StructuredTool
from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import (
    DictInput,
    DropdownInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
)
from langflow.schema import Data


class QuerySchema(BaseModel):
    query: str = Field(..., description="The query to search for.")
    query_type: str = Field(
        "search",
        description="The type of search to perform (e.g., 'news' or 'search').",
    )
    k: int = Field(4, description="The number of results to return.")
    query_params: dict[str, Any] = Field({}, description="Additional query parameters to pass to the API.")


class GoogleSerperAPIComponent(LCToolComponent):
    display_name = "Google Serper API [DEPRECATED]"
    description = "Call the Serper.dev Google Search API."
    name = "GoogleSerperAPI"
    icon = "Google"
    legacy = True
    inputs = [
        SecretStrInput(name="serper_api_key", display_name="Serper API Key", required=True),
        MultilineInput(
            name="query",
            display_name="Query",
        ),
        IntInput(name="k", display_name="Number of results", value=4, required=True),
        DropdownInput(
            name="query_type",
            display_name="Query Type",
            required=False,
            options=["news", "search"],
            value="search",
        ),
        DictInput(
            name="query_params",
            display_name="Query Params",
            required=False,
            value={
                "gl": "us",
                "hl": "en",
            },
            list=True,
        ),
    ]

    def run_model(self) -> Data | list[Data]:
        wrapper = self._build_wrapper(self.k, self.query_type, self.query_params)
        results = wrapper.results(query=self.query)

        # Adjust the extraction based on the `type`
        if self.query_type == "search":
            list_results = results.get("organic", [])
        elif self.query_type == "news":
            list_results = results.get("news", [])
        else:
            list_results = []

        data_list = []
        for result in list_results:
            result["text"] = result.pop("snippet", "")
            data_list.append(Data(data=result))
        self.status = data_list
        return data_list

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="google_search",
            description="Search Google for recent results.",
            func=self._search,
            args_schema=self.QuerySchema,
        )

    def _build_wrapper(
        self,
        k: int = 5,
        query_type: str = "search",
        query_params: dict | None = None,
    ) -> GoogleSerperAPIWrapper:
        wrapper_args = {
            "serper_api_key": self.serper_api_key,
            "k": k,
            "type": query_type,
        }

        # Add query_params if provided
        if query_params:
            wrapper_args.update(query_params)  # Merge with additional query params

        # Dynamically pass parameters to the wrapper
        return GoogleSerperAPIWrapper(**wrapper_args)

    def _search(
        self,
        query: str,
        k: int = 5,
        query_type: str = "search",
        query_params: dict | None = None,
    ) -> dict:
        wrapper = self._build_wrapper(k, query_type, query_params)
        return wrapper.results(query=query)
