from typing import Any

import httpx
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MultilineInput
from langflow.schema import Data


class WikidataSearchSchema(BaseModel):
    query: str = Field(..., description="The search query for Wikidata")


class WikidataAPIWrapper(BaseModel):
    """Wrapper around Wikidata API."""

    wikidata_api_url: str = "https://www.wikidata.org/w/api.php"

    def results(self, query: str) -> list[dict[str, Any]]:
        # Define request parameters for Wikidata API
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "search": query,
            "language": "en",
        }

        # Send request to Wikidata API
        response = httpx.get(self.wikidata_api_url, params=params)
        response.raise_for_status()
        response_json = response.json()

        # Extract and return search results
        return response_json.get("search", [])

    def run(self, query: str) -> list[dict[str, Any]]:
        try:
            results = self.results(query)
            if not results:
                msg = "No search results found for the given query."

                raise ToolException(msg)

            # Process and structure the results
            return [
                {
                    "label": result.get("label", ""),
                    "description": result.get("description", ""),
                    "concepturi": result.get("concepturi", ""),
                    "id": result.get("id", ""),
                }
                for result in results
            ]

        except Exception as e:
            error_message = f"Error in Wikidata Search API: {e!s}"

            raise ToolException(error_message) from e


class WikidataAPIComponent(LCToolComponent):
    display_name = "Wikidata API"
    description = "Performs a search using the Wikidata API."
    name = "WikidataAPI"

    inputs = [
        MultilineInput(
            name="query",
            display_name="Query",
            info="The text query for similarity search on Wikidata.",
            required=True,
        ),
    ]

    def build_tool(self) -> Tool:
        wrapper = WikidataAPIWrapper()

        # Define the tool using StructuredTool and wrapper's run method
        tool = StructuredTool.from_function(
            name="wikidata_search_api",
            description="Perform similarity search on Wikidata API",
            func=wrapper.run,
            args_schema=WikidataSearchSchema,
        )

        self.status = "Wikidata Search API Tool for Langchain"

        return tool

    def run_model(self) -> list[Data]:
        tool = self.build_tool()

        results = tool.run({"query": self.query})

        # Transform the API response into Data objects
        data = [
            Data(
                text=result["label"],
                metadata={
                    "id": result["id"],
                    "concepturi": result["concepturi"],
                    "description": result["description"],
                },
            )
            for result in results
        ]

        self.status = data  # type: ignore[assignment]

        return data
