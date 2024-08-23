from typing import List
import httpx

from langchain_core.tools import StructuredTool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, StrInput, NestedDictInput
from langflow.field_typing import Tool

from pydantic.v1 import Field, create_model


api_base_url = "https://datastax.glean.com/rest/api/v1/"


def search(glean_access_token, field_name: str, values: List[dict]) -> list:
    try:
        url = f"{api_base_url}search"
        headers = {"Authorization": f"Bearer {glean_access_token}"}
        response = httpx.get(url, {"fieldName": field_name, "values": values}, headers)

        return response.json()
    except Exception as e:
        return [f"Failed to search: {str(e)}"]


class GleanAPIComponent(LCToolComponent):
    display_name = "Glean Search API"
    description = "Call Glean Search API"
    name = "GleanAPI"

    inputs = [
        SecretStrInput(name="glean_access_token", display_name="Glean Access Token", required=True),
        StrInput(name="field_name", display_name="Field Name", required=True),
        NestedDictInput(name="values", display_name="Values", required=True),
    ]

    def build_tool(self) -> Tool:
        schema_fields = {
            "field_name": (str, Field(..., description="The field to filter.")),
            "values": (list[str], Field(default=[], description="The filters to apply.")),
        }

        GleanSearchSchema = create_model("GleanSearchSchema", **schema_fields)  # type: ignore

        tool = StructuredTool.from_function(
            func=search,
            args_schema=GleanSearchSchema,
            name="glean_search_tool",
            description="A tool that filters on a field with Glean.",
        )

        return tool
