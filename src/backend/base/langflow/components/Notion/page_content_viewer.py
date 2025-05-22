from typing import Any

import requests

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, MultiselectInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict
from langflow.schema.message import Message


class NotionPageContent(Component):
    """A component that retrieves and displays the content of a Notion page.

    Uses a two-step selection process: first select a database, then select a page from that database.
    """

    display_name: str = "Page Content Viewer"
    description: str = "View the content of a Notion page using database-first selection."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-content-viewer"
    icon: str = "NotionDirectoryLoader"

    # Store database pages cache
    _database_pages_cache: dict[str, list[dict[str, Any]]] = {}
    # Store database cache
    _cached_databases: list[dict[str, Any]] = []

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="database_id",
            display_name="Database",
            info="Select a database to list its pages",
            options=["Loading databases..."],
            value="Loading databases...",
            real_time_refresh=True,
            required=True,
        ),
        DropdownInput(
            name="page_id",
            display_name="Page",
            info="Select a page to view its content",
            options=["Select a database first..."],
            value="Select a database first...",
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
        BoolInput(
            name="view_first_page",
            display_name="View First Page",
            info="Set to True to automatically view the first available page from the first database.",
            required=False,
            value=True,
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="message", display_name="Page Message", method="view_page_message"),
        Output(name="blocks", display_name="Block List", method="view_blocks_as_data"),
    ]

    def fetch_databases(self) -> list[dict[str, Any]]:
        """Fetch available databases from Notion API."""
        if not self.notion_secret:
            self.log("No Notion secret provided.")
            return []

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        try:
            self.log("Fetching databases from Notion API...")
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"filter": {"value": "database", "property": "object"}},
                timeout=10,
            )
            response.raise_for_status()

            databases = []
            for db in response.json().get("results", []):
                # Get the database title
                title = "Untitled Database"
                if "title" in db:
                    title_parts = db.get("title", [])
                    if title_parts:
                        title = "".join(part.get("plain_text", "") for part in title_parts)

                databases.append({"id": db["id"], "title": title or "Untitled Database"})

            # Cache the databases
            self.__class__._cached_databases = databases

            self.log(f"Found {len(databases)} databases.")
            return sorted(databases, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []

    def fetch_database_pages(self, database_id: str) -> list[dict[str, Any]]:
        """Fetch pages from a specific database."""
        # Extract the pure ID if it's in the format "Name (ID)"
        if "(" in database_id and database_id.endswith(")"):
            database_id = database_id.split("(")[-1].rstrip(")")

        if not database_id or database_id in ["Loading databases...", "No databases found"]:
            return []

        # Check if we have cached pages for this database
        if database_id in self._database_pages_cache:
            return self._database_pages_cache[database_id]

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        try:
            self.log(f"Fetching pages from database: {database_id}")
            # Query database pages
            response = requests.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=headers,
                json={"page_size": 100},  # Get up to 100 pages
                timeout=15,
            )
            response.raise_for_status()

            pages = []
            for page in response.json().get("results", []):
                # Get the page title from properties
                title = "Untitled Page"
                if "properties" in page:
                    # Look for title property (can be named "title", "Name", etc.)
                    for prop_value in page["properties"].values():
                        if prop_value.get("type") == "title":
                            title_parts = prop_value.get("title", [])
                            if title_parts:
                                title = "".join(part.get("plain_text", "") for part in title_parts)
                                break

                pages.append({"id": page["id"], "title": title, "last_edited_time": page.get("last_edited_time", "")})

            # Sort by title
            pages_sorted = sorted(pages, key=lambda x: x["title"].lower())

            # Cache the results
            self._database_pages_cache[database_id] = pages_sorted

            self.log(f"Found {len(pages_sorted)} pages in database {database_id}")
            return pages_sorted
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pages from database: {e!s}")
            return []
        else:
            return pages_sorted

    def fetch_available_block_types(self, page_id: str, headers: dict) -> set[str]:
        """Fetch and return a unique set of block types available in the page."""
        block_types = set()
        cursor = None

        try:
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
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching block types: {e}")
            return set()
        else:
            return block_types

    def get_actual_page_id(self) -> str:
        """Extract the actual page ID from the format 'Title (ID)'."""
        if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
            return ""

        # Extract ID from "Title (ID)" format
        if "(" in self.page_id and self.page_id.endswith(")"):
            return self.page_id.split("(")[-1].rstrip(")")

        return self.page_id  # Fallback to the original value

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                # Fetch the databases
                databases = self.fetch_databases()

                # Prepare the dropdown options with "Database Name (ID)" format
                options = [f"{db['title']} ({db['id']})" for db in databases]

                if not options:
                    options = ["No databases found"]

                build_config["database_id"]["options"] = options
                if options and options[0] != "No databases found":
                    build_config["database_id"]["value"] = options[0]

                # Reset page dropdown
                build_config["page_id"]["options"] = ["Select a database first..."]
                build_config["page_id"]["value"] = "Select a database first..."

                # Reset block types
                build_config["block_types"]["options"] = []
                build_config["block_types"]["value"] = []
                build_config["block_types"]["advanced"] = True

            # When database_id changes
            if field_name == "database_id":
                if field_value and field_value not in ["Loading databases...", "No databases found"]:
                    # Fetch pages for this database
                    pages = self.fetch_database_pages(field_value)

                    # Prepare the dropdown options with "Page Name (ID)" format
                    page_options = [f"{page['title']} ({page['id']})" for page in pages]

                    if not page_options:
                        page_options = ["No pages found"]

                    build_config["page_id"]["options"] = page_options
                    if page_options and page_options[0] != "No pages found":
                        build_config["page_id"]["value"] = page_options[0]
                    else:
                        build_config["page_id"]["value"] = "No pages found"

                    # Reset block types
                    build_config["block_types"]["options"] = []
                    build_config["block_types"]["value"] = []
                    build_config["block_types"]["advanced"] = True
                else:
                    build_config["page_id"]["options"] = ["Select a database first..."]
                    build_config["page_id"]["value"] = "Select a database first..."
                    build_config["block_types"]["options"] = []
                    build_config["block_types"]["value"] = []
                    build_config["block_types"]["advanced"] = True

            # When page_id changes
            if field_name == "page_id" and field_value not in ["Select a database first...", "No pages found"]:
                actual_page_id = self.get_actual_page_id()
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

    def get_first_available_page_id(self) -> str:
        """Get the first available page ID from the first available database."""
        # Use cached databases or fetch them
        if not self.__class__._cached_databases:
            self.fetch_databases()

        if not self.__class__._cached_databases:
            self.log("No databases found")
            return ""

        # Get the first database
        first_db = self.__class__._cached_databases[0]
        db_id = first_db["id"]
        self.log(f"Using first database: {first_db['title']} ({db_id})")

        # Get pages for this database
        pages = self.fetch_database_pages(db_id)
        if not pages:
            self.log(f"No pages found in database {first_db['title']}")
            return ""

        # Get the first page
        first_page = pages[0]
        page_id = first_page["id"]
        self.log(f"Using first page: {first_page['title']} ({page_id})")
        return page_id

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
        # Check if we're in tool mode
        if hasattr(self, "view_first_page") and self.view_first_page:
            self.log("Tool mode activated with view_first_page=True")
            page_id = self.get_first_available_page_id()
            if not page_id:
                return Message(text="No pages available. Please check Notion database access.")
        else:
            # Normal mode - use the selected page
            if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
                return Message(text="Please select a valid page")

            # Get the actual page ID
            page_id = self.get_actual_page_id()

        if not page_id:
            return Message(text="Invalid page ID format or no page available")

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            # First fetch page data for title
            page_data = self.fetch_page_data(page_id, headers)
            page_title = "Untitled Page"
            if "properties" in page_data:
                for prop_value in page_data["properties"].values():
                    if prop_value.get("type") == "title":
                        title_parts = prop_value.get("title", [])
                        if title_parts:
                            page_title = "".join(part.get("plain_text", "") for part in title_parts)
                            break

            # Then fetch blocks
            blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
            blocks_response = requests.get(blocks_url, headers=headers, timeout=15)
            blocks_response.raise_for_status()
            blocks_data = blocks_response.json()
            content = self.parse_blocks(blocks_data.get("results", []))

            if not content.strip():
                # Include both title and page URL in the message
                content = f"# {page_title}\n\nPage has no accessible content. No URL available."
            else:
                # Include a header with the page title and URL for context
                content = f"# {page_title}\n\nPage URL: {page_data.get('url', 'No URL available')}\n\n{content}"

            return Message(text=content)
        except requests.exceptions.RequestException as e:
            return Message(text=f"Error fetching page: {e}")

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

        # Check if we're in tool mode
        if hasattr(self, "view_first_page") and self.view_first_page:
            self.log("Tool mode activated with view_first_page=True")
            page_id = self.get_first_available_page_id()
            if not page_id:
                error_data = Data(data={"error": "No pages available. Check database access."})
                data_list.append(error_data)
                self.status = data_list  # type: ignore[assignment]
                return data_list
        else:
            # Normal mode - use the selected page
            if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
                error_data = Data(data={"error": "Please select a valid page."})
                data_list.append(error_data)
                self.status = data_list  # type: ignore[assignment]
                return data_list

            # Get the actual page ID
            page_id = self.get_actual_page_id()

        if not page_id:
            error_data = Data(data={"error": "Invalid page ID format or no page available"})
            data_list.append(error_data)
            # Using type ignore for assignment to self.status as other components do
            self.status = data_list  # type: ignore[assignment]
            return data_list

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            # Get page info for reference
            page_data = self.fetch_page_data(page_id, headers)
            page_title = "Untitled Page"
            if "properties" in page_data:
                for prop_value in page_data["properties"].values():
                    if prop_value.get("type") == "title":
                        title_parts = prop_value.get("title", [])
                        if title_parts:
                            page_title = "".join(part.get("plain_text", "") for part in title_parts)
                            break

            # Add page metadata as the first item
            data_list.append(
                Data(
                    data={
                        "type": "page_info",
                        "id": page_id,
                        "title": page_title,
                        "url": page_data.get("url", ""),
                        "created_time": page_data.get("created_time", ""),
                        "last_edited_time": page_data.get("last_edited_time", ""),
                    }
                )
            )

            # Get the actual blocks
            blocks_data = self.fetch_blocks_for_dataframe(page_id, headers)

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
