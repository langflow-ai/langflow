import requests
from langchain.tools import StructuredTool
from pydantic import BaseModel

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import SecretStrInput
from lfx.schema.data import Data


class NotionUserList(LCToolComponent):
    display_name = "List Users "
    description = "Retrieve users from Notion."
    documentation = "https://docs.langflow.org/integrations/notion/list-users"
    icon = "NotionDirectoryLoader"

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    class NotionUserListSchema(BaseModel):
        pass

    def run_model(self) -> list[Data]:
        users = self._list_users()
        records = []
        combined_text = ""

        for user in users:
            output = "User:\n"
            for key, value in user.items():
                output += f"{key.replace('_', ' ').title()}: {value}\n"
            output += "________________________\n"

            combined_text += output
            records.append(Data(text=output, data=user))

        self.status = records
        return records

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="notion_list_users",
            description="Retrieve users from Notion.",
            func=self._list_users,
            args_schema=self.NotionUserListSchema,
        )

    def _list_users(self) -> list[dict]:
        url = "https://api.notion.com/v1/users"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = data["results"]

        users = []
        for user in results:
            user_data = {
                "id": user["id"],
                "type": user["type"],
                "name": user.get("name", ""),
                "avatar_url": user.get("avatar_url", ""),
            }
            users.append(user_data)

        return users
