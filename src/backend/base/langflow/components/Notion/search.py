import logging
from typing import Any

import pandas as pd
import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, MessageTextInput, SecretStrInput
from langflow.schema import DataFrame
from langflow.template import Output


class NotionSearch(Component):
    """Component that searches Notion objects."""

    display_name: str = "Search"
    description: str = (
        "Searches for pages, databases, users, or all objects. "
        "Also allows searching for blocks, but only based on the page title."
    )
    documentation: str = "https://developers.notion.com/reference/search"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="Notion integration token.",
            required=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Text to search for in the objects or, in the case of blocks, in the page title.",
            tool_mode=True,
        ),
        DropdownInput(
            name="filter_value",
            display_name="Filter Type",
            info=(
                "Select the type of object to be searched: 'page', 'database', 'user', 'all' (all objects) "
                "or 'block' (search within the content of blocks, but filtering by page title)."
            ),
            options=["page", "database", "user", "all", "block"],
            value="page",
            tool_mode=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="sort_direction",
            display_name="Sort Direction",
            info="Direction of the result sorting (applies to pages and databases).",
            options=["ascending", "descending"],
            value="descending",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="results", display_name="Search Results", method="search"),
    ]

    def get_page_title(self, page: dict) -> str:
        """Extracts the title of a page using the 'title' type property."""
        try:
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    if title_array:
                        return "".join(item.get("plain_text", "") for item in title_array)
        except (KeyError, TypeError):
            logging.exception("Error extracting page title:")
        return "Untitled"

    def search(self) -> DataFrame:
        """Performs a search in Notion objects (pages, databases, users, all objects, or block content)."""
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        # Normaliza a query para ignorar espaços extras e maiúsculas
        query_str = self.query.strip().lower()

        # 1) Busca de usuários
        if self.filter_value == "user":
            url = "https://api.notion.com/v1/users"
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                users = response.json().get("results", [])
                filtered_users = [
                    user
                    for user in users
                    if query_str in user.get("name", "").lower()
                    or ("person" in user and query_str in user["person"].get("email", "").lower())
                ]
                user_data = [
                    {
                        "id": user["id"],
                        "type": "user",
                        "name": user.get("name", "Unnamed User"),
                        "url": "N/A",
                        "last_edited_time": "N/A",
                    }
                    for user in filtered_users
                ]
                return DataFrame(pd.DataFrame(user_data))
            except requests.exceptions.RequestException as e:
                return DataFrame(pd.DataFrame({"error": [f"Error searching for users: {e}"]}))

        # 2) Busca em blocos (filtrando somente pelo título da página)
        elif self.filter_value == "block":
            pages_url = "https://api.notion.com/v1/search"
            data = {
                "query": self.query,
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": self.sort_direction, "timestamp": "last_edited_time"},
            }
            try:
                response = requests.post(pages_url, headers=headers, json=data, timeout=10)
                response.raise_for_status()
                pages = response.json().get("results", [])
                block_results: list[dict[str, Any]] = []
                for page in pages:
                    # Checks if the page title contains the query
                    page_title = self.get_page_title(page).lower()
                    if query_str in page_title:
                        page_id = page.get("id")
                        # Search page blocks
                        blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
                        blocks_response = requests.get(blocks_url, headers=headers, timeout=10)
                        blocks_response.raise_for_status()
                        blocks = blocks_response.json().get("results", [])
                        block_results.extend(
                            {
                                "page_id": page_id,
                                "block_id": block.get("id"),
                                "block_type": block.get("type"),
                                "page_title": self.get_page_title(page),
                                "url": page.get("url", "N/A"),
                            }
                            for block in blocks
                        )

                if block_results:
                    block_results_df = pd.DataFrame(block_results)
                else:
                    block_results_df = pd.DataFrame([{"message": "No corresponding block found."}])
                return DataFrame(block_results_df)
            except requests.exceptions.RequestException as e:
                return DataFrame(pd.DataFrame({"error": [f"Error searching for blocks: {e}"]}))

        # 3) General search for 'page', 'database' or 'all'
        else:
            url = "https://api.notion.com/v1/search"
            data = {
                "query": self.query,
                "sort": {"direction": self.sort_direction, "timestamp": "last_edited_time"},
            }
            if self.filter_value in ["page", "database"]:
                data["filter"] = {"value": self.filter_value, "property": "object"}
            try:
                response = requests.post(url, headers=headers, json=data, timeout=10)
                response.raise_for_status()
                results = response.json().get("results", [])
                search_results = []
                for result in results:
                    result_data = {
                        "id": result.get("id"),
                        "type": result.get("object"),
                        "last_edited_time": result.get("last_edited_time"),
                    }
                    if result.get("object") == "page":
                        result_data["name"] = self.get_page_title(result)
                        result_data["url"] = result.get("url", "N/A")
                    elif result.get("object") == "database":
                        title_list = result.get("title", [])
                        if isinstance(title_list, list) and title_list:
                            result_data["name"] = title_list[0].get("plain_text", "Untitled Database")
                        else:
                            result_data["name"] = "Untitled Database"
                        result_data["url"] = result.get("url", "N/A")
                    else:
                        result_data["name"] = "N/A"
                        result_data["url"] = "N/A"
                    search_results.append(result_data)

                search_results_df = pd.DataFrame(search_results)
                for col in ["id", "type", "name", "url", "last_edited_time"]:
                    if col not in search_results_df.columns:
                        search_results_df[col] = "N/A"
                search_results_df = search_results_df[["id", "type", "name", "url", "last_edited_time"]]
                return DataFrame(search_results_df)
            except requests.exceptions.RequestException as e:
                return DataFrame(pd.DataFrame({"error": [f"Error searching in Notion: {e}"]}))
