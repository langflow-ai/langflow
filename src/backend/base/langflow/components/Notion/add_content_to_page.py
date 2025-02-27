import json
from typing import Any

import requests
from bs4 import BeautifulSoup
from loguru import logger
from markdown import markdown

from langflow.custom import Component
from langflow.inputs import DropdownInput, MultilineInput, SecretStrInput
from langflow.schema import Data, dotdict
from langflow.template import Output

MIN_ROWS_IN_TABLE = 3


class AddContentToPage(Component):
    """A component that adds content to a Notion page by converting markdown to Notion blocks."""

    display_name: str = "Add Content to Page"
    description: str = "Convert markdown text to Notion blocks and append them after the selected block."
    documentation: str = "https://developers.notion.com/reference/patch-block-children"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        MultilineInput(
            name="markdown_text",
            display_name="Markdown Text",
            info="The markdown text to convert to Notion blocks.",
            tool_mode=True,
        ),
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
            info="Select a page to add content to",
            options=["Loading pages..."],
            value="Loading pages...",
            real_time_refresh=True,
            required=True,
        ),
        DropdownInput(
            name="block_id",
            display_name="Insert After Block",
            info="Content will be added after this block",
            options=["Top of Page"],
            value="Top of Page",
            real_time_refresh=True,
            required=True,
        ),
    ]

    outputs = [
        Output(name="data", display_name="Response Data", method="add_content_to_page"),
    ]

    def search_pages(self) -> list[dict[str, Any]]:
        """Search Notion pages shared with the integration."""
        url = "https://api.notion.com/v1/search"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        data = {
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
        }

        try:
            self.log("Searching for pages...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()

            results = response.json().get("results", [])
            self.log(f"Found {len(results)} pages")

            pages = []
            for result in results:
                # Extract page title
                title = "Untitled"
                if "properties" in result:
                    for prop in result["properties"].values():
                        if prop["type"] == "title":
                            title_array = prop.get("title", [])
                            if title_array:
                                title = "".join(part.get("plain_text", "") for part in title_array)
                                break

                pages.append(
                    {
                        "id": result["id"],
                        "title": title,
                        "url": result.get("url", ""),
                    }
                )

        except requests.exceptions.RequestException as e:
            self.log(f"Error searching pages: {e}")
            return []
        else:
            return sorted(pages, key=lambda x: x["title"].lower())

    def get_block_children(self, block_id: str) -> list[dict[str, Any]]:
        """Get children blocks of a given block ID."""
        if not block_id:
            return []

        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            self.log(f"Fetching children for block: {block_id}")
            response = requests.get(url, headers=headers, params={"page_size": 100}, timeout=10)
            response.raise_for_status()

            results = response.json().get("results", [])
            self.log(f"Found {len(results)} child blocks")

            blocks = []
            for block in results:
                block_type = block.get("type", "unknown")
                content = self.get_block_content(block)

                blocks.append(
                    {
                        "id": block["id"],
                        "type": block_type,
                        "content": content,
                        "has_children": block.get("has_children", False),
                    }
                )

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching block children: {e}")
            return []
        else:
            return blocks

    def get_block_content(self, block: dict[str, Any]) -> str:
        """Extract readable content from a block."""
        block_type = block.get("type", "")
        if not block_type or block_type == "unsupported":
            return f"{block_type}"

        block_data = block.get(block_type, {})

        # Handle text-based blocks
        if "rich_text" in block_data:
            rich_text = block_data.get("rich_text", [])
            return "".join(rt.get("plain_text", "") for rt in rich_text)

        # Handle specific block types
        if block_type == "child_page":
            return f"Page: {block_data.get('title', 'Untitled')}"

        if block_type == "child_database":
            return f"Database: {block_data.get('title', 'Untitled')}"

        # Default for any other block types
        return f"{block_type}"

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the component build configuration."""
        try:
            # When notion_secret changes or component initializes
            if field_name is None or field_name == "notion_secret":
                pages = self.search_pages()

                # Build options list and create a lookup dict for page IDs
                page_options = []
                page_tooltips = {}

                for page in pages:
                    title = page["title"]
                    page_id = page["id"]
                    page_options.append(title)
                    page_tooltips[title] = page_id

                # Update the page dropdown
                build_config["page_id"]["options"] = page_options if page_options else ["Loading pages..."]
                if page_options:
                    build_config["page_id"]["value"] = page_options[0]

                # Store the page ID mapping in tooltips
                build_config["page_id"]["tooltips"] = page_tooltips

                # Reset block dropdown
                build_config["block_id"]["options"] = ["Top of Page"]
                build_config["block_id"]["value"] = "Top of Page"

            # When page_id changes
            elif field_name == "page_id" and field_value != "Loading pages...":
                # Get the actual page ID from tooltips
                page_id = build_config["page_id"]["tooltips"].get(field_value)

                if page_id:
                    self.log(f"Selected page: {field_value} (ID: {page_id})")

                    # Fetch blocks for this page
                    blocks = self.get_block_children(page_id)

                    # Build options and tooltips for blocks
                    block_options = []
                    block_tooltips = {}

                    for block in blocks:
                        display_text = (
                            f"{block['type']}: {block['content'][:50]}..." if block["content"] else block["type"]
                        )
                        block_options.append(display_text)
                        block_tooltips[display_text] = block["id"]

                    # Update the block dropdown
                    build_config["block_id"]["options"] = ["Top of Page", *block_options]
                    build_config["block_id"]["value"] = "Top of Page"
                    build_config["block_id"]["tooltips"] = block_tooltips

                    self.log(f"Updated block options: {len(block_options)} blocks")
                else:
                    self.log(f"Could not find page ID for: {field_value}")

        except requests.exceptions.RequestException as e:
            self.log(f"Error updating build config: {e}")

        return build_config

    def add_content_to_page(self) -> Data:
        """Convert markdown text to Notion blocks and append them after the selected block."""
        page_title = self.page_id
        page_id = ""

        try:
            # Use the tooltips to get the page ID and URL
            pages = self.search_pages()
            page_url = ""
            for page in pages:
                if page["title"] == page_title:
                    page_id = page["id"]
                    page_url = page["url"]
                    break

            if not page_id:
                return Data(data={"error": "Could not find page ID for the selected page"})

            # Get block ID if not "Top of Page"
            after_id = ""
            if self.block_id != "Top of Page":
                blocks = self.get_block_children(page_id)
                for block in blocks:
                    display_text = f"{block['type']}: {block['content'][:50]}..." if block["content"] else block["type"]
                    if display_text == self.block_id:
                        after_id = block["id"]
                        break

            # Convert markdown to blocks
            html_text = markdown(self.markdown_text)
            soup = BeautifulSoup(html_text, "html.parser")
            blocks = self.process_node(soup)

            # Prepare request to add content
            url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            headers = {
                "Authorization": f"Bearer {self.notion_secret}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }

            # Explicitly type data as a dictionary to resolve linter error
            data: dict[str, Any] = {"children": blocks}
            if after_id:
                data["after"] = after_id

            # Make the request
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()

            # Return the response data
            result = response.json()
            result["page_id"] = page_id
            result["page_url"] = page_url
            if after_id:
                result["after_block"] = after_id

            return Data(data=result)

        except requests.exceptions.RequestException as e:
            error_message = f"Error adding content to Notion: {e}"
            if hasattr(e, "response") and e.response:
                error_message += f" Status: {e.response.status_code}, Response: {e.response.text}"
            return Data(data={"error": error_message})
        except json.JSONDecodeError as e:
            logger.opt(exception=True).debug("Error decoding JSON response from Notion")
            return Data(data={"error": f"An error occurred while decoding the JSON response: {e}"})

    def process_node(self, node):
        """Process a BeautifulSoup node and convert it to Notion blocks."""
        blocks = []
        if isinstance(node, str):
            text = node.strip()
            if text:
                if text.startswith("#"):
                    heading_level = min(text.count("#", 0, 6), 3)
                    heading_text = text[heading_level:].strip()
                    blocks.append(self.create_block(f"heading_{heading_level}", heading_text))
                else:
                    blocks.append(self.create_block("paragraph", text))
        elif node.name == "h1":
            blocks.append(self.create_block("heading_1", node.get_text(strip=True)))
        elif node.name == "h2":
            blocks.append(self.create_block("heading_2", node.get_text(strip=True)))
        elif node.name == "h3":
            blocks.append(self.create_block("heading_3", node.get_text(strip=True)))
        elif node.name == "p":
            code_node = node.find("code")
            if code_node:
                code_text = code_node.get_text()
                language, code = self.extract_language_and_code(code_text)
                blocks.append(self.create_block("code", code, language=language))
            elif self.is_table(str(node)):
                blocks.extend(self.process_table(node))
            else:
                blocks.append(self.create_block("paragraph", node.get_text(strip=True)))
        elif node.name == "ul":
            blocks.extend(self.process_list(node, "bulleted_list_item"))
        elif node.name == "ol":
            blocks.extend(self.process_list(node, "numbered_list_item"))
        elif node.name == "blockquote":
            blocks.append(self.create_block("quote", node.get_text(strip=True)))
        elif node.name == "hr":
            blocks.append(self.create_block("divider", ""))
        elif node.name == "img":
            blocks.append(self.create_block("image", "", image_url=node.get("src")))
        elif node.name == "a":
            blocks.append(self.create_block("bookmark", node.get_text(strip=True), link_url=node.get("href")))
        elif node.name == "table":
            blocks.extend(self.process_table(node))

        for child in node.children:
            if isinstance(child, str):
                continue
            blocks.extend(self.process_node(child))

        return blocks

    def extract_language_and_code(self, code_text):
        """Extract language and code from a code block."""
        lines = code_text.split("\n")
        language = lines[0].strip()
        code = "\n".join(lines[1:]).strip()
        return language, code

    def is_table(self, text):
        """Check if text represents a markdown table."""
        rows = text.split("\n")
        if len(rows) < MIN_ROWS_IN_TABLE:
            return False

        has_separator = False
        for i, row in enumerate(rows):
            if "|" in row:
                cells = [cell.strip() for cell in row.split("|")]
                cells = [cell for cell in cells if cell]  # Remove empty cells
                if i == 1 and all(set(cell) <= set("-|") for cell in cells):
                    has_separator = True
                elif not cells:
                    return False

        return has_separator

    def process_list(self, node, list_type):
        """Process list nodes and convert them to Notion list blocks."""
        blocks = []
        for item in node.find_all("li", recursive=False):  # Only direct children
            item_text = item.get_text(strip=True)
            checked = item_text.startswith("[x]")
            is_checklist = item_text.startswith("[ ]") or checked

            if is_checklist:
                item_text = item_text.replace("[x]", "").replace("[ ]", "").strip()
                blocks.append(self.create_block("to_do", item_text, checked=checked))
            else:
                blocks.append(self.create_block(list_type, item_text))

            # Process nested lists if any
            nested_ul = item.find("ul")
            if nested_ul:
                blocks.extend(self.process_list(nested_ul, "bulleted_list_item"))
            nested_ol = item.find("ol")
            if nested_ol:
                blocks.extend(self.process_list(nested_ol, "numbered_list_item"))

        return blocks

    def process_table(self, node):
        """Process table nodes and convert them to Notion table blocks."""
        blocks = []
        header_row = node.find("thead").find("tr") if node.find("thead") else None
        body_rows = node.find("tbody").find_all("tr") if node.find("tbody") else []

        if not body_rows and not header_row:
            all_rows = node.find_all("tr")
            if len(all_rows) > 1:
                header_row = all_rows[0]
                body_rows = all_rows[1:]

        if header_row or body_rows:
            table_width = max(
                len(header_row.find_all(["th", "td"])) if header_row else 0,
                *(len(row.find_all(["th", "td"])) for row in body_rows),
            )

            table_block = self.create_block("table", "", table_width=table_width, has_column_header=bool(header_row))
            blocks.append(table_block)

            if header_row:
                header_cells = [cell.get_text(strip=True) for cell in header_row.find_all(["th", "td"])]
                header_row_block = self.create_block("table_row", header_cells)
                blocks.append(header_row_block)

            for row in body_rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
                row_block = self.create_block("table_row", cells)
                blocks.append(row_block)

        return blocks

    def create_block(self, block_type: str, content: str, **kwargs) -> dict[str, Any]:
        """Create a Notion block with the specified type and content."""
        block: dict[str, Any] = {
            "object": "block",
            "type": block_type,
            block_type: {},
        }

        if block_type in {
            "paragraph",
            "heading_1",
            "heading_2",
            "heading_3",
            "bulleted_list_item",
            "numbered_list_item",
            "quote",
        }:
            block[block_type]["rich_text"] = [
                {
                    "type": "text",
                    "text": {"content": content},
                }
            ]
        elif block_type == "to_do":
            block[block_type]["rich_text"] = [
                {
                    "type": "text",
                    "text": {"content": content},
                }
            ]
            block[block_type]["checked"] = kwargs.get("checked", False)
        elif block_type == "code":
            block[block_type]["rich_text"] = [
                {
                    "type": "text",
                    "text": {"content": content},
                }
            ]
            block[block_type]["language"] = kwargs.get("language", "plain text")
        elif block_type == "image":
            block[block_type] = {"type": "external", "external": {"url": kwargs.get("image_url", "")}}
        elif block_type == "divider":
            pass
        elif block_type == "bookmark":
            block[block_type]["url"] = kwargs.get("link_url", "")
        elif block_type == "table":
            block[block_type]["table_width"] = kwargs.get("table_width", 0)
            block[block_type]["has_column_header"] = kwargs.get("has_column_header", False)
            block[block_type]["has_row_header"] = kwargs.get("has_row_header", False)
        elif block_type == "table_row":
            block[block_type]["cells"] = [[{"type": "text", "text": {"content": cell}} for cell in content]]

        return block
