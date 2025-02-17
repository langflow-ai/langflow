import pandas as pd
import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, MessageTextInput, SecretStrInput
from langflow.schema import DataFrame
from langflow.template import Output


class NotionSearch(Component):
    """A component that searches all pages and databases shared with a Notion integration."""

    display_name: str = "Search"
    description: str = "Searches all pages and databases that have been shared with an integration."
    documentation: str = "https://docs.langflow.org/integrations/notion/search"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="The text that the API compares page and database titles against.",
            tool_mode=True,
        ),
        DropdownInput(
            name="filter_value",
            display_name="Filter Type",
            info="Limits the results to either only pages or only databases.",
            options=["page", "database"],
            value="page",
            tool_mode=True,
        ),
        DropdownInput(
            name="sort_direction",
            display_name="Sort Direction",
            info="The direction to sort the results.",
            options=["ascending", "descending"],
            value="descending",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="results", display_name="Search Results", method="search"),
    ]

    def search(self) -> DataFrame:
        """Search Notion pages and databases."""
        url = "https://api.notion.com/v1/search"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        data = {
            "query": self.query,
            "filter": {"value": self.filter_value, "property": "object"},
            "sort": {"direction": self.sort_direction, "timestamp": "last_edited_time"},
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            results = response.json()["results"]

            # Transform results into a list of dicts with flattened structure
            search_results = []
            for result in results:
                result_data = {
                    "id": result["id"],
                    "type": result["object"],
                    "last_edited_time": result["last_edited_time"],
                }

                if result["object"] == "page":
                    result_data["title_or_url"] = result["url"]
                elif result["object"] == "database":
                    if "title" in result and isinstance(result["title"], list) and len(result["title"]) > 0:
                        result_data["title_or_url"] = result["title"][0]["plain_text"]
                    else:
                        result_data["title_or_url"] = "N/A"

                search_results.append(result_data)

            # Convert to DataFrame with ordered columns
            search_results_df = pd.DataFrame(search_results)
            column_order = ["id", "type", "title_or_url", "last_edited_time"]
            search_results_df = search_results_df[column_order]

            return DataFrame(search_results_df)

        except requests.exceptions.RequestException as e:
            return DataFrame(pd.DataFrame({"error": [f"Error searching Notion: {e}"]}))
        except KeyError:
            return DataFrame(pd.DataFrame({"error": ["Unexpected response format from Notion API"]}))
        except (ValueError, TypeError) as e:
            return DataFrame(pd.DataFrame({"error": [f"Error processing search results: {e}"]}))
