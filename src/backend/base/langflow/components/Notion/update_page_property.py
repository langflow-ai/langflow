import json
from typing import Any

import requests
from langchain.tools import StructuredTool
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs.inputs import MultilineInput, SecretStrInput, StrInput
from langflow.schema.data import Data


class NotionPageUpdate(LCToolComponent):
    display_name: str = "Update Page Property "
    description: str = "Update the properties of a Notion page."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-update"
    icon = "NotionDirectoryLoader"

    inputs = [
        StrInput(
            name="page_id",
            display_name="Page ID",
            info="The ID of the Notion page to update.",
        ),
        MultilineInput(
            name="properties",
            display_name="Properties",
            info="The properties to update on the page (as a JSON string or a dictionary).",
        ),
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    class NotionPageUpdateSchema(BaseModel):
        page_id: str = Field(..., description="The ID of the Notion page to update.")
        properties: str | dict[str, Any] = Field(
            ..., description="The properties to update on the page (as a JSON string or a dictionary)."
        )

    def run_model(self) -> Data:
        result = self._update_notion_page(self.page_id, self.properties)
        if isinstance(result, str):
            # An error occurred, return it as text
            return Data(text=result)
        # Success, return the updated page data
        output = "Updated page properties:\n"
        for prop_name, prop_value in result.get("properties", {}).items():
            output += f"{prop_name}: {prop_value}\n"
        return Data(text=output, data=result)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="update_notion_page",
            description="Update the properties of a Notion page. "
            "IMPORTANT: Use the tool to check the Database properties for more details before using this tool.",
            func=self._update_notion_page,
            args_schema=self.NotionPageUpdateSchema,
        )

    def _update_notion_page(self, page_id: str, properties: str | dict[str, Any]) -> dict[str, Any] | str:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",  # Use the latest supported version
        }

        # Parse properties if it's a string
        if isinstance(properties, str):
            try:
                parsed_properties = json.loads(properties)
            except json.JSONDecodeError as e:
                error_message = f"Invalid JSON format for properties: {e}"
                logger.exception(error_message)
                return error_message

        else:
            parsed_properties = properties

        data = {"properties": parsed_properties}

        try:
            logger.info(f"Sending request to Notion API: URL: {url}, Data: {json.dumps(data)}")
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            updated_page = response.json()

            logger.info(f"Successfully updated Notion page. Response: {json.dumps(updated_page)}")
        except requests.exceptions.HTTPError as e:
            error_message = f"HTTP Error occurred: {e}"
            if e.response is not None:
                error_message += f"\nStatus code: {e.response.status_code}"
                error_message += f"\nResponse body: {e.response.text}"
            logger.exception(error_message)
            return error_message
        except requests.exceptions.RequestException as e:
            error_message = f"An error occurred while making the request: {e}"
            logger.exception(error_message)
            return error_message
        except Exception as e:  # noqa: BLE001
            error_message = f"An unexpected error occurred: {e}"
            logger.exception(error_message)
            return error_message

        return updated_page

    def __call__(self, *args, **kwargs):
        return self._update_notion_page(*args, **kwargs)
