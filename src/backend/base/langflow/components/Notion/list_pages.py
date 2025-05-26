from typing import Any

import pandas as pd
import requests
from loguru import logger

from langflow.custom import Component
from langflow.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.schema import DataFrame, dotdict
from langflow.template import Output


class NotionListPages(Component):
    """A component that lists and queries pages from a Notion database."""

    display_name: str = "List Pages"
    description: str = "Query a Notion database with filtering and sorting options."
    documentation: str = "https://docs.langflow.org/integrations/notion/list-pages"
    icon: str = "NotionDirectoryLoader"

    # Store database properties globally
    _database_properties: dict[str, Any] = {}
    # Cache for database list
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
        DropdownInput(
            name="filter_property",
            display_name="Filter Property",
            info="Property to filter by",
            options=[],
            value="",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="filter_operator",
            display_name="Filter Operator",
            info="Operator to use for filtering",
            options=[],
            value="",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="filter_value",
            display_name="Filter Value",
            info="Value to filter by",
        ),
        DropdownInput(
            name="sort_property",
            display_name="Sort Property",
            info="Property to sort by",
            options=[],
            value="",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="sort_direction",
            display_name="Sort Direction",
            info="Direction to sort",
            options=["ascending", "descending"],
            value="ascending",
        ),
        IntInput(
            name="page_size",
            display_name="Page Size",
            info="Maximum number of pages to return",
            value=100,
            advanced=True,
        ),
        BoolInput(
            name="list_all_pages",
            display_name="List All Pages",
            info="Set to True to list all pages from the first available database.",
            required=False,
            value=False,
            tool_mode=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="pages", display_name="Pages", method="list_pages"),
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

            # Cache databases for later use
            self.__class__._cached_databases = results

            self.log(f"Found {len(results)} databases.")
            # Fix for TRY300: Move return inside else block
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []
        else:
            return results

    def fetch_database_properties(self, database_id: str) -> dict[str, Any]:
        """Fetch properties of a specific database."""
        # Extract the pure ID if it's in the format "Name (ID)"
        if "(" in database_id and database_id.endswith(")"):
            database_id = database_id.split("(")[-1].rstrip(")")

        if not database_id or database_id == "Loading databases...":
            return {}

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            self.log(f"Fetching properties for database: {database_id}")
            response = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json().get("properties", {})
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching database properties: {e!s}")
            return {}

    def build_filter_condition(
        self, property_name: str, property_type: str, operator: str, value: str
    ) -> dict[str, Any]:
        """Build a Notion filter condition based on property type and operator."""
        if not value.strip():
            return {}

        if property_type in {"title", "rich_text"}:
            return {"property": property_name, property_type: {operator: value}}
        if property_type == "number":
            try:
                num_value = float(value)
            except ValueError:
                return {}
            else:
                return {"property": property_name, property_type: {operator: num_value}}
        elif property_type in {"select", "status"}:
            return {"property": property_name, property_type: {operator: value}}
        elif property_type == "multi_select":
            values = [v.strip() for v in value.split(",")]
            if operator == "contains":
                return {"property": property_name, property_type: {operator: values[0] if values else ""}}
            return {"property": property_name, property_type: {operator: value}}
        elif property_type == "date":
            return {"property": property_name, property_type: {operator: value}}
        elif property_type == "checkbox":
            return {"property": property_name, property_type: {operator: value.lower() in ("true", "1", "yes", "y")}}
        else:
            return {"property": property_name, "rich_text": {operator: value}}

    def get_actual_database_id(self) -> str:
        """Extract the database ID from the selected database name format: 'Name (ID)'."""
        if "(" in self.database_id and self.database_id.endswith(")"):
            return self.database_id.split("(")[-1].rstrip(")")
        return self.database_id  # Fallback

    def list_pages(self) -> DataFrame:
        """Query pages from the selected Notion database with filtering and sorting."""
        # Check if we're in tool mode using list_all_pages
        if hasattr(self, "list_all_pages") and self.list_all_pages:
            self.log("Tool mode activated with list_all_pages=True")

            # Use the cached databases or fetch them if needed
            if not self.__class__._cached_databases:
                self.fetch_databases()

            # If we have databases, use the first one
            if self.__class__._cached_databases:
                first_db = self.__class__._cached_databases[0]
                db_id = first_db["id"]
                db_name = ""
                title_array = first_db.get("title", [])
                for title_part in title_array:
                    if "plain_text" in title_part:
                        db_name += title_part["plain_text"]

                if not db_name:
                    db_name = "Untitled"

                self.log(f"Using first available database: {db_name} ({db_id})")
                actual_database_id = db_id

                # Fetch properties for this database
                self._database_properties = self.fetch_database_properties(actual_database_id)
            else:
                error_msg = "No databases available."
                self.log(error_msg)
                return DataFrame(pd.DataFrame({"error": [error_msg]}))
        else:
            # Normal mode, use the selected database from dropdown
            if not self.database_id or self.database_id == "Loading databases...":
                error_msg = "Please select a valid database."
                return DataFrame(pd.DataFrame({"error": [error_msg]}))

            # Get the actual database ID from the formatted database name
            actual_database_id = self.get_actual_database_id()
            self.log(f"Using selected database ID: {actual_database_id}")

            # Ensure we have database properties
            if not self._database_properties:
                self._database_properties = self.fetch_database_properties(actual_database_id)

        # Build query payload
        query_payload = {"page_size": self.page_size}

        # Add filter if provided and not in tool mode
        # Fix for E501: Break long line into multiple lines
        if (
            not (hasattr(self, "list_all_pages") and self.list_all_pages)
            and self.filter_property
            and self.filter_operator
            and self.filter_value
        ):
            prop_info = self._database_properties.get(self.filter_property, {})
            prop_type = prop_info.get("type", "text")

            condition = self.build_filter_condition(
                self.filter_property, prop_type, self.filter_operator, self.filter_value
            )
            if condition:
                query_payload["filter"] = condition

        # Add sort if provided and not in tool mode
        if not (hasattr(self, "list_all_pages") and self.list_all_pages) and self.sort_property:
            query_payload["sorts"] = [{"property": self.sort_property, "direction": self.sort_direction}]

        # Make the request
        try:
            self.log(f"Querying database {actual_database_id} with payload: {query_payload}")
            response = requests.post(
                f"https://api.notion.com/v1/databases/{actual_database_id}/query",
                headers={
                    "Authorization": f"Bearer {self.notion_secret}",
                    "Content-Type": "application/json",
                    "Notion-Version": "2022-06-28",
                },
                json=query_payload,
                timeout=10,
            )
            response.raise_for_status()
            results = response.json()["results"]
            self.log(f"Received {len(results)} pages from Notion API.")

            # Transform results
            pages_data = []
            for page in results:
                page_data = {
                    "id": page["id"],
                    "url": page["url"],
                    "created_time": page["created_time"],
                    "last_edited_time": page["last_edited_time"],
                }

                # Add properties as columns with formatted values
                for prop_name, prop_value in page["properties"].items():
                    value = self.format_property_value(prop_value)
                    page_data[prop_name] = value

                pages_data.append(page_data)

            # Convert to DataFrame
            pages_df = pd.DataFrame(pages_data)

            # Reorder columns
            main_cols = ["id", "url", "created_time", "last_edited_time"]
            other_cols = [col for col in pages_df.columns if col not in main_cols]
            pages_df = pages_df[main_cols + sorted(other_cols)]

            return DataFrame(pages_df)

        except requests.exceptions.RequestException as e:
            error_msg = f"Error querying Notion database: {e}"
            self.log(error_msg)
            return DataFrame(pd.DataFrame({"error": [error_msg]}))
        except (ValueError, KeyError, TypeError) as e:
            error_msg = f"Error processing database response: {e}"
            logger.opt(exception=True).debug("Error processing Notion database response")
            self.log(error_msg)
            return DataFrame(pd.DataFrame({"error": [error_msg]}))

    def format_property_value(self, prop_value: dict[str, Any]) -> str:
        """Format a Notion property value for display in the DataFrame."""
        prop_type = prop_value["type"]

        if prop_type in ("title", "rich_text"):
            texts = prop_value.get(prop_type, [])
            return " ".join(text.get("plain_text", "") for text in texts)

        if prop_type == "select":
            select_value = prop_value.get("select")
            return select_value.get("name", "") if select_value else ""

        if prop_type == "multi_select":
            values = prop_value.get("multi_select", [])
            return ", ".join(value.get("name", "") for value in values)

        if prop_type == "date":
            date = prop_value.get("date")
            if not date:
                return ""
            start = date.get("start", "")
            end = date.get("end", "")
            return f"{start} to {end}" if end else start

        if prop_type == "checkbox":
            return str(prop_value.get("checkbox", False))

        if prop_type == "number":
            return str(prop_value.get("number", 0))

        if prop_type == "url":
            return prop_value.get("url", "")

        if prop_type == "email":
            return prop_value.get("email", "")

        if prop_type == "phone_number":
            return prop_value.get("phone_number", "")

        if prop_type == "files":
            files = prop_value.get("files", [])
            return ", ".join(f.get("name", "") for f in files)

        return str(prop_value.get(prop_type, ""))

    def get_operators_for_type(self, prop_type: str) -> list[str]:
        """Get valid filter operators for a given property type."""
        base_operators = {
            "title": ["equals", "does_not_equal", "contains", "does_not_contain", "starts_with", "ends_with"],
            "rich_text": ["equals", "does_not_equal", "contains", "does_not_contain", "starts_with", "ends_with"],
            "number": [
                "equals",
                "does_not_equal",
                "greater_than",
                "less_than",
                "greater_than_or_equal_to",
                "less_than_or_equal_to",
            ],
            "select": ["equals", "does_not_equal", "is_empty", "is_not_empty"],
            "multi_select": ["contains", "does_not_contain", "is_empty", "is_not_empty"],
            "date": ["equals", "before", "after", "on_or_before", "on_or_after", "is_empty", "is_not_empty"],
            "checkbox": ["equals"],
            "files": ["is_empty", "is_not_empty"],
            "url": ["equals", "does_not_equal", "contains", "does_not_contain", "starts_with", "ends_with"],
            "email": ["equals", "does_not_equal", "contains", "does_not_contain", "starts_with", "ends_with"],
            "phone_number": ["equals", "does_not_equal", "contains", "does_not_contain", "starts_with", "ends_with"],
            "status": ["equals", "does_not_equal"],
        }

        return base_operators.get(prop_type, ["equals", "does_not_equal", "contains", "does_not_contain"])

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                databases = self.fetch_databases()
                # Format options as "Name (ID)"
                formatted_dbs = []
                for db in databases:
                    # Extract title from Notion's response structure
                    db_name = ""
                    title_array = db.get("title", [])
                    for title_part in title_array:
                        if "plain_text" in title_part:
                            db_name += title_part["plain_text"]

                    # Use "Untitled" if no title found
                    if not db_name:
                        db_name = "Untitled"

                    db_id = db["id"]
                    formatted_name = f"{db_name} ({db_id})"
                    formatted_dbs.append(formatted_name)

                build_config["database_id"]["options"] = formatted_dbs
                if databases:
                    build_config["database_id"]["value"] = formatted_dbs[0]

            # When database_id changes
            if field_name == "database_id":
                if field_value and field_value != "Loading databases...":
                    # Extract actual database ID
                    actual_db_id = self.get_actual_database_id()
                    self._database_properties = self.fetch_database_properties(actual_db_id)

                    # Update property options for filter and sort
                    property_options = list(self._database_properties.keys())

                    build_config["filter_property"]["options"] = property_options
                    build_config["sort_property"]["options"] = property_options

                    if property_options:
                        build_config["filter_property"]["value"] = property_options[0]
                        build_config["sort_property"]["value"] = property_options[0]

                        # Set initial operators based on first property type
                        first_prop = self._database_properties[property_options[0]]
                        operators = self.get_operators_for_type(first_prop["type"])
                        build_config["filter_operator"]["options"] = operators
                        build_config["filter_operator"]["value"] = operators[0] if operators else ""
                else:
                    self._database_properties = {}
                    build_config["filter_property"]["options"] = []
                    build_config["sort_property"]["options"] = []

            # When filter_property changes
            if field_name == "filter_property" and field_value:
                prop_info = self._database_properties.get(field_value, {})
                prop_type = prop_info.get("type", "text")
                operators = self.get_operators_for_type(prop_type)

                build_config["filter_operator"]["options"] = operators
                build_config["filter_operator"]["value"] = operators[0] if operators else ""

                # Update value field info based on property type
                value_info = "Enter value"
                if prop_type == "select":
                    options = prop_info.get("select", {}).get("options", [])
                    value_info = f"Valid options: {', '.join(opt['name'] for opt in options)}"
                elif prop_type == "multi_select":
                    options = prop_info.get("multi_select", {}).get("options", [])
                    value_info = f"Valid options (comma separated): {', '.join(opt['name'] for opt in options)}"
                elif prop_type == "date":
                    value_info = "Enter date in YYYY-MM-DD format"
                elif prop_type == "number":
                    value_info = "Enter a number"
                elif prop_type == "checkbox":
                    value_info = "Enter 'true' or 'false'"

                build_config["filter_value"]["info"] = value_info

        except (KeyError, TypeError, ValueError) as e:
            self.log(f"Error updating build config: {e!s}")
            build_config["database_id"]["options"] = ["Error loading databases"]
            build_config["database_id"]["value"] = "Error loading databases"

        return build_config
