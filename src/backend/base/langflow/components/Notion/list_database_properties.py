from typing import Any

import requests
from loguru import logger

from langflow.custom import Component
from langflow.inputs import DropdownInput, SecretStrInput
from langflow.schema import Data, dotdict
from langflow.template import Output


class NotionDatabaseProperties(Component):
    """A component that retrieves properties of a Notion database."""

    display_name: str = "List Database Properties"
    description: str = "Retrieve properties of a Notion database."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-database-properties"
    icon: str = "NotionDirectoryLoader"

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
            info="Select a database",
            options=["Loading databases..."],
            value="Loading databases...",
            real_time_refresh=True,
            required=True,
        ),
    ]

    outputs = [
        Output(name="data", display_name="Database Properties", method="get_database_properties"),
    ]

    def fetch_databases(self) -> list[dict[str, Any]]:
        """Fetch available databases from Notion API."""
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"filter": {"value": "database", "property": "object"}},
                timeout=10,
            )
            response.raise_for_status()

            databases = []
            for db in response.json().get("results", []):
                # Extracts the title from the title array
                title_array = db.get("title", [])
                title = ""
                for title_part in title_array:
                    # Use plain_text that already comes correctly formatted
                    if "plain_text" in title_part:
                        title += title_part["plain_text"]

                # If no title is found, use a default
                if not title:
                    title = "Untitled Database"

                databases.append({"id": db["id"], "title": title})

            return sorted(databases, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []

    def update_build_config(self, build_config: dotdict, _field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                # Fetch the databases
                databases = self.fetch_databases()

                # Prepare the dropdown options using the titles
                options = [db["title"] for db in databases]
                # Create mapping of title to ID
                id_map = {db["title"]: db["id"] for db in databases}

                # Update the dropdown
                build_config["database_id"] = {
                    "name": "database_id",
                    "type": "str",
                    "required": True,
                    "show": True,
                    "display_name": "Database",
                    "options": options,
                    "value": options[0] if options else "",
                    "id_map": id_map,  # Stores the mapping for later use
                }

        except (requests.exceptions.RequestException, KeyError) as e:
            self.log(f"Error updating build config: {e!s}")
            build_config["database_id"] = {
                "name": "database_id",
                "type": "str",
                "required": True,
                "show": True,
                "display_name": "Database",
                "options": ["Error loading databases"],
                "value": "Error loading databases",
            }

        return build_config

    def get_database_properties(self) -> Data:
        """Retrieve properties of a Notion database."""
        if not self.database_id or self.database_id == "Loading databases...":
            return Data(data={"error": "Please select a valid database."})

        try:
            # Fetch databases again to have the updated mapping
            databases = self.fetch_databases()
            title_to_id = {db["title"]: db["id"] for db in databases}

            # Use the selected title to get the ID
            database_id = title_to_id.get(self.database_id)

            if not database_id:
                return Data(data={"error": f"Database not found: {self.database_id}"})

            headers = {
                "Authorization": f"Bearer {self.notion_secret}",
                "Notion-Version": "2022-06-28",
            }

            response = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Transform the properties into a friendlier format
            properties = {}
            for prop_name, prop_info in data.get("properties", {}).items():
                prop_type = prop_info["type"]
                prop_data = {"type": prop_type, "name": prop_name}

                # Add specific type information
                if prop_type == "select":
                    prop_data["options"] = [opt["name"] for opt in prop_info.get("select", {}).get("options", [])]
                elif prop_type == "multi_select":
                    prop_data["options"] = [opt["name"] for opt in prop_info.get("multi_select", {}).get("options", [])]
                elif prop_type == "status":
                    prop_data["options"] = [opt["name"] for opt in prop_info.get("status", {}).get("options", [])]

                properties[prop_name] = prop_data

            return Data(data=properties)

        except requests.exceptions.RequestException as e:
            error_message = f"Error fetching Notion database properties: {e}"
            if hasattr(e, "response") and e.response is not None:
                error_message += f" Status code: {e.response.status_code}, Response: {e.response.text}"
            return Data(data={"error": error_message})
        except KeyError as e:
            logger.opt(exception=True).debug("Error processing Notion database properties")
            return Data(data={"error": f"Error processing database properties: {e}"})
