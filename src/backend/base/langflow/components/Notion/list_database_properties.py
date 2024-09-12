import requests
from typing import Dict, Union
from pydantic import BaseModel, Field
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, StrInput
from langflow.schema import Data
from langflow.field_typing import Tool
from langchain.tools import StructuredTool


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
        else:
            # Success, return the properties
            return Data(text=str(result), data=result)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="notion_database_properties",
            description="Retrieve properties of a Notion database. Input should include the database ID.",
            func=self._fetch_database_properties,
            args_schema=self.NotionDatabasePropertiesSchema,
        )

    def _fetch_database_properties(self, database_id: str) -> Union[Dict, str]:
        url = f"https://api.notion.com/v1/databases/{database_id}"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",  # Use the latest supported version
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            properties = data.get("properties", {})
            return properties
        except requests.exceptions.RequestException as e:
            return f"Error fetching Notion database properties: {str(e)}"
        except ValueError as e:
            return f"Error parsing Notion API response: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
