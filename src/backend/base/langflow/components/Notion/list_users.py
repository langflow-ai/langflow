import pandas as pd
import requests

from langflow.custom import Component
from langflow.inputs import SecretStrInput
from langflow.schema import DataFrame
from langflow.template import Output


class NotionUserList(Component):
    """A component that retrieves users from Notion."""

    display_name: str = "List Users"
    description: str = "Retrieve users from Notion."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-users"
    icon: str = "NotionDirectoryLoader"

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="users", display_name="Users", method="list_users"),
    ]

    def list_users(self) -> DataFrame:
        """Retrieve users from Notion."""
        url = "https://api.notion.com/v1/users"
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
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

            # Convert to DataFrame with ordered columns
            users_df = pd.DataFrame(users)
            column_order = ["id", "name", "type", "avatar_url"]
            users_df = users_df[column_order]

            return DataFrame(users_df)

        except requests.exceptions.RequestException as e:
            return DataFrame(pd.DataFrame({"error": [f"Error fetching Notion users: {e}"]}))
        except KeyError:
            return DataFrame(pd.DataFrame({"error": ["Unexpected response format from Notion API"]}))
        except (ValueError, TypeError) as e:
            return DataFrame(pd.DataFrame({"error": [f"Error processing user data: {e}"]}))
