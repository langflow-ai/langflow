import requests
from langchain.tools import StructuredTool
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import SecretStrInput, StrInput
from langflow.schema import Data


class NotionDatabaseProperties(LCToolComponent):
    display_name: str = "List Database Properties "
    description: str = "Retrieve properties of a Notion database."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-database-properties"
    icon = "NotionDirectoryLoader"

    inputs = [
        StrInput(
            name="database_id",
            display_name="Database ID",
            info="The ID of the Notion database.",
        ),
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    class NotionDatabasePropertiesSchema(BaseModel):
        database_id: str = Field(..., description="The ID of the Notion database.")

    def run_model(self) -> Data:
        result = self._fetch_database_properties(self.database_id)
        if isinstance(result, str):
            # An error occurred, return it as text
            return Data(text=result)
        # Success, return the properties
        return Data(text=str(result), data=result)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="notion_database_properties",
            description="Retrieve properties of a Notion database. Input should include the database ID.",
            func=self._fetch_database_properties,
            args_schema=self.NotionDatabasePropertiesSchema,
        )

    def _fetch_database_properties(self, database_id: str) -> dict | str:
        url = f"https://api.notion.com/v1/databases/{database_id}"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",  # Use the latest supported version
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("properties", {})
        except requests.exceptions.RequestException as e:
            return f"Error fetching Notion database properties: {e}"
        except ValueError as e:
            return f"Error parsing Notion API response: {e}"
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error fetching Notion database properties")
            return f"An unexpected error occurred: {e}"
