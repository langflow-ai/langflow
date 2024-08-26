import httpx

from typing import List, Optional
from urllib.parse import urljoin

from langchain_core.tools import StructuredTool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, StrInput, NestedDictInput, IntInput
from langflow.field_typing import Tool

from pydantic.v1 import Field, create_model


class GleanAPIComponent(LCToolComponent):
    display_name = "Glean Search API"
    description = "Call Glean Search API"
    name = "GleanAPI"

    inputs = [
        StrInput(
            name="glean_api_url",
            display_name="Glean API URL",
            required=True,
        ),
        SecretStrInput(name="glean_access_token", display_name="Glean Access Token", required=True),
        StrInput(name="query", display_name="Query", required=True),
        IntInput(name="page_size", display_name="Page Size", value=10),
        StrInput(name="field_name", display_name="Field Name", required=False),
        NestedDictInput(name="values", display_name="Values", required=False),
    ]

    @staticmethod
    def search(
        glean_api_url: str,
        glean_access_token,
        query: str,
        page_size: int = 10,
        field_name: Optional[str] = None,
        values: Optional[List[dict]] = None,
    ) -> list:
        try:
            # Build the payload
            payload = {
                "query": query,
                "pageSize": page_size,
                "facetFilters": [{"field_name": field_name, "values": values}],
            }

            url = urljoin(glean_api_url, "search")
            headers = {"Authorization": f"Bearer {glean_access_token}"}
            response = httpx.post(url, json=payload, headers=headers)

            return response.json()
        except Exception as e:
            return [f"Failed to search: {str(e)}"]

    def build_tool(self) -> Tool:
        schema_fields = {
            "glean_api_url": (str, Field(..., description="The Glean API URL.")),
            "glean_access_token": (str, Field(..., description="The Glean access token.")),
            "query": (str, Field(..., description="The search query.")),
            "page_size": (int, Field(default=10, description="The page size.")),
            "field_name": (str, Field(default=None, description="The field to filter.")),
            "values": (list[str], Field(default=None, description="The filters to apply.")),
        }

        GleanSearchSchema = create_model("GleanSearchSchema", **schema_fields)  # type: ignore

        tool = StructuredTool.from_function(
            func=self.search,
            args_schema=GleanSearchSchema,
            name="glean_search_tool",
            description="A tool that filters on a field with Glean.",
        )

        return tool
