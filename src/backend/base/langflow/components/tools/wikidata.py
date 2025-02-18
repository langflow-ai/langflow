import httpx
import requests

from langflow.custom import Component
from langflow.inputs import MultilineInput
from langflow.io import Output
from langflow.schema import DataFrame


class WikidataComponent(Component):
    """Component for performing searches using the Wikidata API.

    This component allows users to search Wikidata and returns results
    in a DataFrame format, providing detailed entity information.
    """

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
        Output(
            display_name="Results",
            name="results",
            type_=DataFrame,
            method="search_wikidata",
        ),
    ]

    def search_wikidata(self) -> DataFrame:
        """Search Wikidata and return results as a DataFrame."""
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
                return DataFrame([{"error": "No search results found for the given query."}])

            # Transform the API response into a DataFrame
            df_results = [
                {
                    "label": result["label"],
                    "id": result.get("id", ""),
                    "url": result.get("url", ""),
                    "description": result.get("description", ""),
                    "concepturi": result.get("concepturi", ""),
                    "full_text": f"{result['label']}: {result.get('description', '')}",
                }
                for result in results
            ]

            return DataFrame(df_results)

        except (httpx.HTTPStatusError, requests.HTTPError) as e:
            error_message = f"HTTP Error in Wikidata Search API: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except (KeyError, ValueError) as e:
            error_message = f"Data parsing error in Wikidata API response: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
        except (httpx.RequestError, ConnectionError) as e:
            error_message = f"Connection error in Wikidata search: {e!s}"
            self.log(error_message)
            return DataFrame([{"error": error_message}])
