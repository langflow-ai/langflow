import requests
from langchain.tools import StructuredTool
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import SecretStrInput, StrInput
from langflow.schema import Data


class NotionPageContent(LCToolComponent):
    display_name = "Page Content Viewer "
    description = "Retrieve the content of a Notion page as plain text."
    documentation = "https://docs.langflow.org/integrations/notion/page-content-viewer"
    icon = "NotionDirectoryLoader"

    inputs = [
        StrInput(
            name="page_id",
            display_name="Page ID",
            info="The ID of the Notion page to retrieve.",
        ),
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    class NotionPageContentSchema(BaseModel):
        page_id: str = Field(..., description="The ID of the Notion page to retrieve.")

    def run_model(self) -> Data:
        result = self._retrieve_page_content(self.page_id)
        if isinstance(result, str) and result.startswith("Error:"):
            # An error occurred, return it as text
            return Data(text=result)
        # Success, return the content
        return Data(text=result, data={"content": result})

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="notion_page_content",
            description="Retrieve the content of a Notion page as plain text.",
            func=self._retrieve_page_content,
            args_schema=self.NotionPageContentSchema,
        )

    def _retrieve_page_content(self, page_id: str) -> str:
        blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
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

    def __call__(self, *args, **kwargs):
        return self._retrieve_page_content(*args, **kwargs)
