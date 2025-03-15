from typing import Any

import pandas as pd
import requests
from loguru import logger

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, SecretStrInput
from langflow.io import Output
from langflow.schema import DataFrame, dotdict


class NotionDatabaseProperties(Component):
    """A component that retrieves properties of a Notion database."""

    display_name: str = "List Database Properties"
    description: str = "Retrieve properties of a Notion database as a structured table."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-database-properties"
    icon: str = "NotionDirectoryLoader"

    # Class variable to store current database options
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
            display_name="Database Name",
            info="Select a database by name",
            options=["Loading databases..."],
            value="Loading databases...",
            real_time_refresh=True,
            required=True,
        ),
        BoolInput(
            name="list_properties",
            display_name="List Database Properties",
            info="Set to True to list the properties of the first available database.",
            required=False,
            value=True,
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="dataframe", display_name="Database Properties", method="get_properties_as_dataframe"),
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
            results = response.json().get("results", [])

            # Cache the databases
            self.__class__._cached_databases = results

            self.log(f"Found {len(results)} databases.")
            return results
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []
        else:
            return results

    def update_build_config(self, build_config: dotdict, _: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                databases = self.fetch_databases()
                # Format options as "Name (ID)"
                formatted_dbs = []
                for db in databases:
                    db_name = db.get("title", [{}])[0].get("text", {}).get("content", "Untitled")
                    db_id = db["id"]
                    formatted_name = f"{db_name} ({db_id})"
                    formatted_dbs.append(formatted_name)

                build_config["database_id"]["options"] = formatted_dbs
                if databases:
                    build_config["database_id"]["value"] = formatted_dbs[0]

                # Map formatted names to original IDs for API calls
                id_mapping = {}
                for db in databases:
                    db_name = db.get("title", [{}])[0].get("text", {}).get("content", "Untitled")
                    db_id = db["id"]
                    formatted_key = f"{db_name} ({db_id})"
                    id_mapping[formatted_key] = db_id
                build_config["database_id"]["tooltips"] = id_mapping

        except (ValueError, KeyError) as e:
            self.log(f"Error updating build config: {e!s}")

            build_config["database_id"]["options"] = ["Error loading databases"]
            build_config["database_id"]["value"] = "Error loading databases"

        return build_config

    def get_properties_as_dataframe(self) -> DataFrame:
        """Retrieve properties of a Notion database as a DataFrame."""
        # Check if we're in tool mode using list_properties
        if hasattr(self, "list_properties") and self.list_properties:
            self.log("Tool mode activated with list_properties=True")

            # Use the cached databases or fetch them if needed
            if not self.__class__._cached_databases:
                self.fetch_databases()

            # If we have databases, use the first one
            if self.__class__._cached_databases:
                first_db = self.__class__._cached_databases[0]
                db_id = first_db["id"]
                db_name = first_db.get("title", [{}])[0].get("text", {}).get("content", "Untitled")
                self.log(f"Using first available database: {db_name} ({db_id})")
                database_id = db_id
            else:
                error_df = pd.DataFrame([{"error": "No databases available."}])
                return DataFrame(error_df)
        else:
            # Normal mode, use the selected database from dropdown
            if not self.database_id or self.database_id == "Loading databases...":
                # Return an empty DataFrame with an error message
                error_df = pd.DataFrame([{"error": "Please select a valid database."}])
                return DataFrame(error_df)

            # Extract the pure ID if it's in the format "Name (ID)"
            database_id = self.database_id
            if "(" in database_id and database_id.endswith(")"):
                database_id = database_id.split("(")[-1].rstrip(")")

        try:
            self.log(f"Getting properties for database ID: {database_id}")

            headers = {
                "Authorization": f"Bearer {self.notion_secret}",
                "Notion-Version": "2022-06-28",
            }

            response = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Prepare data for DataFrame rows
            rows = []
            for prop_name, prop_info in data.get("properties", {}).items():
                prop_type = prop_info["type"]
                prop_id = prop_info.get("id", "")

                row = {
                    "name": prop_name,
                    "type": prop_type,
                    "id": prop_id,
                }

                # Add specific type information
                if prop_type == "select":
                    options = [opt["name"] for opt in prop_info.get("select", {}).get("options", [])]
                    row["options"] = ", ".join(options) if options else ""
                elif prop_type == "multi_select":
                    options = [opt["name"] for opt in prop_info.get("multi_select", {}).get("options", [])]
                    row["options"] = ", ".join(options) if options else ""
                elif prop_type == "status":
                    options = [opt["name"] for opt in prop_info.get("status", {}).get("options", [])]
                    row["options"] = ", ".join(options) if options else ""
                elif prop_type == "relation":
                    # Get relation database ID
                    relation_id = prop_info.get("relation", {}).get("database_id")
                    if relation_id:
                        row["relation_database_id"] = relation_id

                rows.append(row)

            # Create DataFrame
            if not rows:
                # Return empty DataFrame with column headers
                empty_df = pd.DataFrame(columns=["name", "type", "id", "options", "relation_database_id"])
                return DataFrame(empty_df)

            # Convert to pandas DataFrame and sort by name
            properties_df = pd.DataFrame(rows).sort_values("name").reset_index(drop=True)

            # Ensure all expected columns exist
            for col in ["options", "relation_database_id"]:
                if col not in properties_df.columns:
                    properties_df[col] = ""

            # Return as DataFrame
            return DataFrame(properties_df)

        except requests.exceptions.RequestException as e:
            error_message = f"Error fetching Notion database properties: {e}"
            if hasattr(e, "response") and e.response is not None:
                error_message += f" Status code: {e.response.status_code}, Response: {e.response.text}"
            error_df = pd.DataFrame([{"error": error_message}])
            return DataFrame(error_df)
        except KeyError as e:
            logger.opt(exception=True).debug("Error processing Notion database properties")
            error_message = f"Error processing database properties: {e}"
            error_df = pd.DataFrame([{"error": error_message}])
            return DataFrame(error_df)
