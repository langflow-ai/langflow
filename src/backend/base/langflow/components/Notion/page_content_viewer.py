from typing import Any

import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, MultiselectInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict
from langflow.schema.message import Message


class NotionPageContentViewer(Component):
    """A component that retrieves and displays the content of a Notion page.

    The page selection is implemented as a dropdown populated with page names,
    mirroring the behavior of the Update Page Property component.
    """

    display_name: str = "Page Content Viewer"
    description: str = "View the content of a Notion page with a dynamically populated dropdown for page selection."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-content-viewer"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="page_id",
            display_name="Page",
            info="Select a page to view its content",
            options=["Loading pages..."],
            value="Loading pages...",
            real_time_refresh=True,
            required=True,
        ),
        MultiselectInput(
            name="block_types",
            display_name="Block Types",
            info="Select block types to include. Leave empty to include all.",
            options=[],
            value=[],
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="data", display_name="Page Message", method="view_page"),
        Output(name="blocks", display_name="Block List", method="view_blocks"),
    ]

    def fetch_pages(self) -> list[dict[str, Any]]:
        """Fetch available pages from the Notion API and return a sorted list with each page's id and title."""
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        try:
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"filter": {"value": "page", "property": "object"}},
                timeout=10,
            )
            response.raise_for_status()

            pages = []
            for page in response.json().get("results", []):
                title = "Untitled Page"
                if "properties" in page:
                    # Look for title property (either "title" or "Name")
                    title_prop = page["properties"].get("title", page["properties"].get("Name", {}))
                    if title_prop and "title" in title_prop:
                        title_parts = title_prop.get("title", [])
                        if title_parts:
                            title = "".join(part.get("plain_text", "") for part in title_parts)
                pages.append({"id": page["id"], "title": title or "Untitled Page"})

            return sorted(pages, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pages: {e}")
            return []

    def fetch_available_block_types(self, page_id: str, headers: dict) -> set[str]:
        """Fetch and return a unique set of block types available in the page."""
        block_types = set()
        cursor = None

        while True:
            params: dict[str, Any] = {}
            if cursor:
                params["start_cursor"] = cursor

            response = requests.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            for block in data.get("results", []):
                block_type = block.get("type")
                if block_type:
                    block_types.add(block_type)
                if block.get("has_children"):
                    child_types = self.fetch_available_block_types(block.get("id"), headers)
                    block_types.update(child_types)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return block_types

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the component build configuration, populating the page dropdown with page titles.

        and associating tooltips with their corresponding IDs.
        """
        try:
            if field_name is None or field_name == "notion_secret":
                pages = self.fetch_pages()
                options = [page["title"] for page in pages]
                build_config["page_id"]["options"] = options
                if options:
                    build_config["page_id"]["value"] = options[0]
                tooltips = {page["title"]: page["id"] for page in pages}
                build_config["page_id"]["tooltips"] = tooltips
                build_config["block_types"]["options"] = []
                build_config["block_types"]["value"] = []
                build_config["block_types"]["advanced"] = True

            elif field_name == "page_id" and field_value != "Loading pages...":
                pages = self.fetch_pages()
                title_to_id = {page["title"]: page["id"] for page in pages}
                actual_page_id = title_to_id.get(field_value)

                if actual_page_id:
                    headers = {
                        "Authorization": f"Bearer {self.notion_secret}",
                        "Notion-Version": "2022-06-28",
                    }
                    block_types = sorted(self.fetch_available_block_types(actual_page_id, headers))
                    build_config["block_types"]["options"] = block_types
                    build_config["block_types"]["advanced"] = False
                else:
                    build_config["block_types"]["options"] = []
                    build_config["block_types"]["advanced"] = True
                build_config["block_types"]["value"] = []

        except KeyError as e:
            self.log(f"Error updating build config: {e}")
        return build_config

    def fetch_block_text(self, block_id: str, headers: dict) -> str:
        """Recursively fetch aggregated text content from the block with the given block_id, handling pagination."""
        text = ""
        cursor = None
        while True:
            params: dict[str, Any] = {}
            if cursor:
                params["start_cursor"] = cursor
            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            for block in data.get("results", []):
                block_type = block.get("type")
                if hasattr(self, "block_types") and self.block_types and block_type not in self.block_types:
                    continue
                if block_type:
                    block_data = block.get(block_type, {})
                    texts = block_data.get("rich_text") or block_data.get("text", [])
                    for text_item in texts:
                        text += text_item.get("plain_text", "") + "\n"
                if block.get("has_children"):
                    text += self.fetch_block_text(block.get("id"), headers) + "\n"
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return text.strip()

    def fetch_filtered_blocks(self, block_id: str, headers: dict) -> list:
        """Recursively fetch blocks filtered by selected block types, handling pagination."""
        blocks_list = []
        cursor = None
        while True:
            params: dict[str, Any] = {}
            if cursor:
                params["start_cursor"] = cursor
            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            for block in data.get("results", []):
                block_type = block.get("type")
                if block_type:
                    if self.block_types and block_type in self.block_types:
                        blocks_list.append(
                            {
                                "type": block_type,
                                "content": self.extract_block_content(block),
                                "has_children": block.get("has_children", False),
                                "id": block.get("id"),
                            }
                        )
                    if block.get("has_children"):
                        child_blocks = self.fetch_filtered_blocks(block.get("id"), headers)
                        blocks_list.extend(child_blocks)
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return blocks_list

    def extract_block_content(self, block: dict) -> str:
        """Extract the text content from a block based on its type."""
        block_type = block.get("type")
        if not block_type:
            return ""
        block_data = block.get(block_type, {})
        text = ""
        rich_text = block_data.get("rich_text", [])
        for text_item in rich_text:
            text += text_item.get("plain_text", "")
        if block_type == "to_do":
            checked = "✓ " if block_data.get("checked", False) else "☐ "
            text = checked + text
        elif block_type.startswith("heading_"):
            level = int(block_type[-1])
            text = "#" * level + " " + text
        elif block_type == "bulleted_list_item":
            text = "• " + text
        elif block_type == "numbered_list_item":
            text = "1. " + text
        return text

    def view_page(self) -> Message:
        """Fetch and return the aggregated text content of the selected Notion page as a Message output.

        Uses the page_id dropdown value to retrieve the corresponding page via its actual ID.
        """
        if not self.page_id or self.page_id == "Loading pages...":
            return Message(text="Please select a valid page")
        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)
        if not actual_page_id:
            return Message(text="Page not found")
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }
        try:
            content = self.fetch_block_text(actual_page_id, headers)
            if not content.strip():
                page_response = requests.get(
                    f"https://api.notion.com/v1/pages/{actual_page_id}", headers=headers, timeout=10
                )
                page_response.raise_for_status()
                page_data = page_response.json()
                title = "Untitled Page"
                if "properties" in page_data:
                    title_prop = page_data["properties"].get("title", page_data["properties"].get("Name", {}))
                    if title_prop and "title" in title_prop:
                        title_parts = title_prop.get("title", [])
                        if title_parts:
                            title = "".join(part.get("plain_text", "") for part in title_parts)
                content = title
            return Message(text=content.strip())
        except requests.exceptions.RequestException as e:
            return Message(text=f"Error fetching page: {e}")

    def view_blocks(self) -> list[Data]:
        """Fetch and return the list of blocks (filtered by selected block types) of the selected Notion page.

        Uses the page_id dropdown value to retrieve the corresponding page via its actual ID.
        """
        if not self.page_id or self.page_id == "Loading pages...":
            return [Data(data={"error": "Please select a valid page"})]
        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)
        if not actual_page_id:
            return [Data(data={"error": "Page not found"})]
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }
        try:
            blocks = self.fetch_filtered_blocks(actual_page_id, headers)
            if not blocks and self.block_types:
                warning_message = "No blocks of selected types (" + ", ".join(self.block_types) + ") found"
                return [Data(data={"warning": warning_message})]
            return [Data(data=block) for block in blocks]
        except requests.exceptions.RequestException as e:
            return [Data(data={"error": f"Error fetching blocks: {e}"})]
