import requests
from loguru import logger

from langflow.custom import Component
from langflow.inputs import MessageTextInput, SecretStrInput
from langflow.template import Output


class NotionPageContent(Component):
    """A component that retrieves the content of a Notion page as plain text."""

    display_name: str = "Page Content Viewer"
    description: str = "Retrieve the content of a Notion page as plain text."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-content-viewer"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        MessageTextInput(
            name="page_id",
            display_name="Page ID",
            info="The ID of the Notion page to retrieve.",
            tool_mode=True,
        ),
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="message", display_name="Page Content", method="get_page_content"),
    ]

    def get_page_content(self) -> str:
        """Retrieve the content of a Notion page as plain text."""
        blocks_url = f"https://api.notion.com/v1/blocks/{self.page_id}/children?page_size=100"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }
        try:
            blocks_response = requests.get(blocks_url, headers=headers, timeout=10)
            blocks_response.raise_for_status()
            blocks_data = blocks_response.json()
            return self.parse_blocks(blocks_data.get("results", []))
        except requests.exceptions.RequestException as e:
            error_message = f"Error: Failed to retrieve Notion page content. {e}"
            if hasattr(e, "response") and e.response is not None:
                error_message += f" Status code: {e.response.status_code}, Response: {e.response.text}"
            return error_message
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error retrieving Notion page content")
            return f"Error: An unexpected error occurred while retrieving Notion page content. {e}"

    def parse_blocks(self, blocks: list) -> str:
        content = ""
        for block in blocks:
            block_type = block.get("type")
            if block_type in {"paragraph", "heading_1", "heading_2", "heading_3", "quote"}:
                content += self.parse_rich_text(block[block_type].get("rich_text", [])) + "\n\n"
            elif block_type in {"bulleted_list_item", "numbered_list_item"}:
                content += self.parse_rich_text(block[block_type].get("rich_text", [])) + "\n"
            elif block_type == "to_do":
                content += self.parse_rich_text(block["to_do"].get("rich_text", [])) + "\n"
            elif block_type == "code":
                content += self.parse_rich_text(block["code"].get("rich_text", [])) + "\n\n"
            elif block_type == "image":
                content += f"[Image: {block['image'].get('external', {}).get('url', 'No URL')}]\n\n"
            elif block_type == "divider":
                content += "---\n\n"
        return content.strip()

    def parse_rich_text(self, rich_text: list) -> str:
        return "".join(segment.get("plain_text", "") for segment in rich_text)
