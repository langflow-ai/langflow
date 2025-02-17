import json

import requests
from loguru import logger

from langflow.custom import Component
from langflow.inputs import MessageTextInput, MultilineInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class NotionPageUpdate(Component):
    """A component that updates properties of a Notion page."""

    display_name: str = "Update Page Property"
    description: str = "Update the properties of a Notion page."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-update"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        MessageTextInput(
            name="page_id",
            display_name="Page ID",
            info="The ID of the Notion page to update.",
            tool_mode=True,
        ),
        MultilineInput(
            name="properties",
            display_name="Properties",
            info="The properties to update on the page (as a JSON string or a dictionary).",
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
        Output(name="data", display_name="Updated Page", method="update_page"),
    ]

    def update_page(self) -> Data:
        """Update properties of a Notion page."""
        if not self.page_id:
            return Data(data={"error": "Page ID is required"})

        if not self.properties or not self.properties.strip():
            return Data(data={"error": "Properties cannot be empty"})

        url = f"https://api.notion.com/v1/pages/{self.page_id}"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        # Parse properties if it's a string
        try:
            parsed_properties = json.loads(self.properties)
            if not isinstance(parsed_properties, dict):
                return Data(data={"error": "Properties must be a valid JSON object"})
        except json.JSONDecodeError as e:
            error_message = f"Invalid JSON format for properties: {e}"
            logger.exception(error_message)
            return Data(data={"error": error_message})

        data = {"properties": parsed_properties}

        try:
            logger.info(f"Sending request to Notion API: URL: {url}, Data: {json.dumps(data)}")
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            updated_page = response.json()

            logger.info(f"Successfully updated Notion page. Response: {json.dumps(updated_page)}")
            return Data(data=updated_page)

        except requests.exceptions.HTTPError as e:
            error_message = f"HTTP Error occurred: {e}"
            if e.response is not None:
                error_message += f"\nStatus code: {e.response.status_code}"
                error_message += f"\nResponse body: {e.response.text}"
            logger.exception(error_message)
            return Data(data={"error": error_message})

        except requests.exceptions.RequestException as e:
            error_message = f"An error occurred while making the request: {e}"
            logger.exception(error_message)
            return Data(data={"error": error_message})

        except Exception as e:  # noqa: BLE001
            error_message = f"An unexpected error occurred: {e}"
            logger.exception(error_message)
            return Data(data={"error": error_message})
