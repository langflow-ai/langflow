import httpx
from httpx import HTTPError
from langchain_core.tools import ToolException

from langflow.custom import Component
from langflow.helpers.data import data_to_text
from langflow.io import MultilineInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


class WikidataComponent(Component):
    display_name = "Wikidata"
    description = "Performs a search using the Wikidata API."
    icon = "Wikipedia"

    inputs = [
        MultilineInput(
            name="query",
            display_name="Query",
            info="The text query for similarity search on Wikidata.",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="fetch_content"),
        Output(display_name="Message", name="text", method="fetch_content_text"),
    ]

    def fetch_content(self) -> list[Data]:
        try:
            # Define request parameters for Wikidata API
            params = {
                "action": "wbsearchentities",
                "format": "json",
                "search": self.query,
                "language": "en",
            }

            # Send request to Wikidata API
            wikidata_api_url = "https://www.wikidata.org/w/api.php"
            response = httpx.get(wikidata_api_url, params=params)
            response.raise_for_status()
            response_json = response.json()

            # Extract search results
            results = response_json.get("search", [])

            if not results:
                return [Data(data={"error": "No search results found for the given query."})]

            # Transform the API response into Data objects
            data = [
                Data(
                    text=f"{result['label']}: {result.get('description', '')}",
                    data={
                        "label": result["label"],
                        "id": result.get("id"),
                        "url": result.get("url"),
                        "description": result.get("description", ""),
                        "concepturi": result.get("concepturi"),
                    },
                )
                for result in results
            ]

            self.status = data
        except HTTPError as e:
            error_message = f"HTTP Error in Wikidata Search API: {e!s}"
            raise ToolException(error_message) from None
        except KeyError as e:
            error_message = f"Data parsing error in Wikidata API response: {e!s}"
            raise ToolException(error_message) from None
        except ValueError as e:
            error_message = f"Value error in Wikidata API: {e!s}"
            raise ToolException(error_message) from None
        else:
            return data

    def fetch_content_text(self) -> Message:
        data = self.fetch_content()
        result_string = data_to_text("{text}", data)
        self.status = result_string
        return Message(text=result_string)
