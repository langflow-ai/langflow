from typing import Any

import requests

from langflow.custom import Component
from langflow.inputs import DropdownInput, MultiselectInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict
from langflow.schema.message import Message


class NotionPageContent(Component):
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
        Output(name="message", display_name="Page Message", method="view_page_message"),
        Output(name="blocks", display_name="Block List", method="view_blocks_as_data"),
    ]

    def fetch_pages(self) -> list[dict[str, Any]]:
        """Fetch available pages from the Notion API and return a sorted list with each page's id and title.

        Handles pagination to ensure all pages are fetched.
        """
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        pages = []
        next_cursor = None
        has_more = True

        try:
            while has_more:
                payload = {
                    "filter": {"value": "page", "property": "object"},
                    "page_size": 100,  # Maximum allowed by Notion API
                }

                if next_cursor:
                    payload["start_cursor"] = next_cursor

                response = requests.post(
                    "https://api.notion.com/v1/search",
                    headers=headers,
                    json=payload,
                    timeout=15,
                )
                response.raise_for_status()

                response_data = response.json()

                for page in response_data.get("results", []):
                    title = "Untitled Page"
                    if "properties" in page:
                        title_prop = page["properties"].get("title", page["properties"].get("Name", {}))
                        if title_prop and "title" in title_prop:
                            title_parts = title_prop.get("title", [])
                            if title_parts:
                                title = "".join(part.get("plain_text", "") for part in title_parts)
                    pages.append({"id": page["id"], "title": title or "Untitled Page"})

                has_more = response_data.get("has_more", False)
                next_cursor = response_data.get("next_cursor")

                if not has_more or not next_cursor:
                    break

                self.log(f"Fetched {len(pages)} pages so far, continuing pagination...")

            self.log(f"Successfully fetched {len(pages)} pages from Notion")
            return sorted(pages, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pages: {e}")
            return []

    def fetch_available_block_types(self, page_id: str, headers: dict) -> set[str]:
        """Fetch and return a unique set of block types available in the page."""
        block_types = set()
        cursor = None

        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            response = requests.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers, params=params, timeout=15
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
        """Update the component build configuration, populating the page dropdown with page titles."""
        try:
            if field_name is None or field_name == "notion_secret":
                self.log("Fetching pages from Notion...")
                pages = self.fetch_pages()
                self.log(f"Found {len(pages)} pages")
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
        except requests.exceptions.RequestException as e:
            self.log(f"Unexpected error updating build config: {e}")

        return build_config

    def fetch_block_text(self, block_id: str, headers: dict) -> str:
        """Recursively fetch aggregated text content from the block with the given block_id."""
        text = ""
        cursor = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            response = requests.get(url, headers=headers, params=params, timeout=15)
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

    def fetch_page_data(self, page_id: str, headers: dict) -> dict:
        """Fetch and return the page metadata."""
        page_response = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, timeout=15)
        page_response.raise_for_status()
        return page_response.json()

    def fetch_filtered_blocks(self, block_id: str, headers: dict) -> list:
        """Recursively fetch blocks filtered by selected block types."""
        blocks_list = []
        cursor = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            for block in data.get("results", []):
                block_type = block.get("type")
                if block_type:
                    if not self.block_types or block_type in self.block_types:
                        block_content = self.extract_structured_block_content(block)
                        blocks_list.append(block_content)
                    if block.get("has_children"):
                        child_blocks = self.fetch_filtered_blocks(block.get("id"), headers)
                        blocks_list.append(
                            {
                                "type": "parent_block",
                                "id": block.get("id"),
                                "parent_type": block_type,
                                "children": child_blocks,
                            }
                        )
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

    def extract_structured_block_content(self, block: dict) -> dict:
        """Extract the structured content from a block based on its type."""
        block_type = block.get("type")
        if not block_type:
            return {"type": "unknown", "content": ""}

        block_id = block.get("id")
        created_time = block.get("created_time")
        last_edited_time = block.get("last_edited_time")
        has_children = block.get("has_children", False)

        block_data = block.get(block_type, {})

        result = {
            "id": block_id,
            "type": block_type,
            "created_time": created_time,
            "last_edited_time": last_edited_time,
            "has_children": has_children,
            "text_content": self.extract_block_content(block),
        }

        if block_type == "paragraph":
            result["paragraph"] = self.extract_rich_text(block_data.get("rich_text", []))
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            result["heading"] = self.extract_rich_text(block_data.get("rich_text", []))
            result["level"] = int(block_type[-1])
        elif block_type in ["bulleted_list_item", "numbered_list_item"]:
            result["list_item"] = self.extract_rich_text(block_data.get("rich_text", []))
            result["item_type"] = "bullet" if block_type == "bulleted_list_item" else "number"
        elif block_type == "to_do":
            result["to_do"] = self.extract_rich_text(block_data.get("rich_text", []))
            result["checked"] = block_data.get("checked", False)
        elif block_type == "toggle":
            result["toggle"] = self.extract_rich_text(block_data.get("rich_text", []))
        elif block_type == "code":
            result["code"] = self.extract_rich_text(block_data.get("rich_text", []))
            result["language"] = block_data.get("language", "")
        elif block_type == "image":
            result["image"] = {
                "caption": self.extract_rich_text(block_data.get("caption", [])),
                "type": block_data.get("type"),
            }
            if block_data.get("type") == "external":
                result["image"]["url"] = block_data.get("external", {}).get("url", "")
            elif block_data.get("type") == "file":
                result["image"]["url"] = block_data.get("file", {}).get("url", "")
        elif block_type == "bookmark":
            result["bookmark"] = {
                "url": block_data.get("url", ""),
                "caption": self.extract_rich_text(block_data.get("caption", [])),
            }
        elif block_type == "callout":
            result["callout"] = {
                "text": self.extract_rich_text(block_data.get("rich_text", [])),
                "icon": block_data.get("icon", {}),
            }
        elif block_type == "quote":
            result["quote"] = self.extract_rich_text(block_data.get("rich_text", []))
        elif block_type == "divider":
            result["divider"] = True
        elif block_type == "table":
            result["table"] = {
                "table_width": block_data.get("table_width", 0),
                "has_column_header": block_data.get("has_column_header", False),
                "has_row_header": block_data.get("has_row_header", False),
            }
        elif block_type in ["column_list", "column"]:
            pass
        elif block_type == "link_preview":
            result["link_preview"] = {"url": block_data.get("url", "")}

        result["raw_data"] = block_data
        return result

    def extract_rich_text(self, rich_text_list: list) -> str:
        """Extract plain text from Notion's rich text format."""
        return "".join(segment.get("plain_text", "") for segment in rich_text_list)

    def parse_blocks(self, blocks: list) -> str:
        """Parse Notion blocks into formatted text with appropriate line breaks."""
        content = ""
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"paragraph", "heading_1", "heading_2", "heading_3", "quote"}:
                content += self.extract_rich_text(block[block_type].get("rich_text", [])) + "\n\n"
            elif block_type in {"bulleted_list_item", "numbered_list_item"}:
                content += self.extract_rich_text(block[block_type].get("rich_text", [])) + "\n"
            elif block_type == "to_do":
                checked = "✓ " if block["to_do"].get("checked", False) else "☐ "
                content += checked + self.extract_rich_text(block["to_do"].get("rich_text", [])) + "\n"
            elif block_type == "code":
                content += self.extract_rich_text(block["code"].get("rich_text", [])) + "\n\n"
            elif block_type == "image":
                content += f"[Image: {block['image'].get('external', {}).get('url', 'No URL')}]\n\n"
            elif block_type == "divider":
                content += "---\n\n"
        return content.strip()

    def view_page_message(self) -> Message:
        """Fetch and return the aggregated text content of the selected Notion page with proper formatting."""
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
            blocks_url = f"https://api.notion.com/v1/blocks/{actual_page_id}/children?page_size=100"
            blocks_response = requests.get(blocks_url, headers=headers, timeout=15)
            blocks_response.raise_for_status()
            blocks_data = blocks_response.json()
            content = self.parse_blocks(blocks_data.get("results", []))
            if not content.strip():
                page_response = requests.get(
                    f"https://api.notion.com/v1/pages/{actual_page_id}", headers=headers, timeout=15
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

            return Message(text=content)
        except requests.exceptions.RequestException as e:
            return Message(text=f"Error fetching page: {e}")

    def view_page_structured(self) -> Data:
        """Fetch and return structured data about the Notion page."""
        if not self.page_id or self.page_id == "Loading pages...":
            return Data(data={"error": "Please select a valid page"})

        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)

        if not actual_page_id:
            return Data(data={"error": "Page not found"})

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            page_data = self.fetch_page_data(actual_page_id, headers)
            title = "Untitled Page"
            if "properties" in page_data:
                title_prop = page_data["properties"].get("title", page_data["properties"].get("Name", {}))
                if title_prop and "title" in title_prop:
                    title_parts = title_prop.get("title", [])
                    if title_parts:
                        title = "".join(part.get("plain_text", "") for part in title_parts)

            content = self.fetch_block_text(actual_page_id, headers)

            structured_data = {
                "page_id": actual_page_id,
                "title": title,
                "url": page_data.get("url", ""),
                "created_time": page_data.get("created_time", ""),
                "last_edited_time": page_data.get("last_edited_time", ""),
                "content": content,
                "content_length": len(content),
                "has_content": bool(content.strip()),
                "parent": page_data.get("parent", {}),
                "archived": page_data.get("archived", False),
            }

            if "properties" in page_data:
                properties = {}
                for prop_name, prop_data in page_data["properties"].items():
                    prop_type = prop_data.get("type", "")
                    prop_value = None

                    if prop_type in ["title", "rich_text"]:
                        text_items = prop_data.get(prop_type, [])
                        prop_value = "".join(item.get("plain_text", "") for item in text_items)
                    elif prop_type == "number":
                        prop_value = prop_data.get("number")
                    elif prop_type == "select":
                        select_data = prop_data.get("select")
                        if select_data:
                            prop_value = select_data.get("name")
                    elif prop_type == "multi_select":
                        multi_select = prop_data.get("multi_select", [])
                        prop_value = [item.get("name") for item in multi_select if item.get("name")]  # type: ignore[assignment]
                    elif prop_type == "date":
                        date_data = prop_data.get("date")
                        if date_data:
                            prop_value = {"start": date_data.get("start"), "end": date_data.get("end")}  # type: ignore[assignment]
                    elif prop_type == "checkbox":
                        prop_value = prop_data.get("checkbox")

                    properties[prop_name] = {"type": prop_type, "value": prop_value}

                structured_data["properties"] = properties

            return Data(data=structured_data)

        except requests.exceptions.RequestException as e:
            error_message = f"Error fetching page data: {e}"
            self.log(error_message)
            return Data(data={"error": error_message})

    def fetch_blocks_for_dataframe(self, block_id: str, headers: dict) -> list[dict]:
        """Fetch blocks and format them for a simple, tabular structure."""
        blocks_data = []
        cursor = None

        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            for block in data.get("results", []):
                block_type = block.get("type")
                if not block_type:
                    continue

                if self.block_types and block_type not in self.block_types:
                    continue

                block_content = self.extract_block_content(block)
                block_id = block.get("id")

                blocks_data.append(
                    {
                        "type": block_type,
                        "content": block_content,
                        "id": block_id,
                        "has_children": "Yes" if block.get("has_children", False) else "No",
                    }
                )

                if block.get("has_children"):
                    child_blocks = self.fetch_blocks_for_dataframe(block_id, headers)
                    blocks_data.extend(child_blocks)

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return blocks_data

    def view_blocks_as_data(self) -> list[Data]:
        """Fetch blocks from the selected Notion page and return as a list of Data objects."""
        data_list: list[Data] = []

        if not self.page_id or self.page_id == "Loading pages...":
            error_data = Data(data={"error": "Please select a valid page"})
            data_list.append(error_data)
            # Using type ignore for assignment to self.status as other components do
            self.status = data_list  # type: ignore[assignment]
            return data_list

        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)

        if not actual_page_id:
            error_data = Data(data={"error": "Page not found"})
            data_list.append(error_data)
            # Using type ignore for assignment to self.status as other components do
            self.status = data_list  # type: ignore[assignment]
            return data_list

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            blocks_data = self.fetch_blocks_for_dataframe(actual_page_id, headers)

            if not blocks_data:
                if self.block_types:
                    message = f"No blocks of selected types ({', '.join(self.block_types)}) found"
                    data_list.append(Data(data={"message": message}))
                else:
                    data_list.append(Data(data={"message": "No content found in this page"}))
            else:
                data_list.extend([Data(data=block) for block in blocks_data])

        except requests.exceptions.RequestException as e:
            error_message = f"Error fetching blocks: {e}"
            self.log(error_message)
            data_list.append(Data(data={"error": error_message}))

        # Using type ignore for assignment to self.status as other components do
        self.status = data_list  # type: ignore[assignment]
        return data_list
