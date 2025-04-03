import json
from typing import Any

import pandas as pd
import requests

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.io import Output
from langflow.schema import DataFrame, dotdict


class NotionPageCreator(Component):
    """A component that creates pages in Notion databases with dynamic properties."""

    display_name: str = "Create Page"
    description: str = "Create a new page in a Notion database with dynamic property selection and values."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-create"
    icon: str = "NotionDirectoryLoader"

    # Maximum number of allowed properties
    MAX_PROPERTIES = 10

    # Store database properties globally
    _database_properties: dict[str, Any] = {}

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
        IntInput(
            name="number_of_properties",
            display_name="Number of Properties",
            info="Number of properties to add to the page",
            value=0,
            real_time_refresh=True,
            range_spec=RangeSpec(min=0, max=MAX_PROPERTIES, step=1, step_type="int"),
            advanced=True,  # Start as hidden
        ),
    ]

    outputs = [
        Output(name="dataframe", display_name="Page Data", method="create_page_as_dataframe"),
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
            return response.json().get("results", [])
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []

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
            response = requests.get(f"https://api.notion.com/v1/databases/{database_id}", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json().get("properties", {})
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching database properties: {e!s}")
            return {}

    def format_property_value(self, prop_name: str, prop_info: dict[str, Any], value: str) -> dict[str, Any]:
        """Format a property value based on its type in Notion."""
        prop_type = prop_info["type"]

        self.log(f"Formatting property {prop_name} of type {prop_type} with value {value}")

        try:
            if prop_type == "title":
                return {"title": [{"type": "text", "text": {"content": str(value)}}]}

            if prop_type == "rich_text":
                return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

            if prop_type == "select":
                if not value:
                    return {"select": None}
                return {"select": {"name": str(value)}}

            if prop_type == "multi_select":
                values = [v.strip() for v in str(value).split(",")]
                return {"multi_select": [{"name": v} for v in values if v]}

            if prop_type == "date":
                if not value:
                    return {"date": None}
                if " to " in value:
                    start, end = value.split(" to ")
                    return {"date": {"start": start.strip(), "end": end.strip()}}
                return {"date": {"start": str(value)}}

            if prop_type == "number":
                if not value:
                    return {"number": None}
                try:
                    return {"number": float(value)}
                except ValueError:
                    return {"number": 0}

            elif prop_type == "checkbox":
                return {"checkbox": str(value).lower() in ("true", "1", "yes", "y", "on")}

            elif prop_type == "url":
                return {"url": str(value) if value else None}

            elif prop_type == "email":
                return {"email": str(value) if value else None}

            elif prop_type == "phone_number":
                return {"phone_number": str(value) if value else None}

            elif prop_type == "files":
                if not value:
                    return {"files": []}
                if value.startswith(("http://", "https://")):
                    return {"files": [{"name": value.split("/")[-1], "type": "external", "external": {"url": value}}]}
                return {"files": []}

            elif prop_type == "relation":
                import re

                uuid_regex = re.compile(
                    r"^[0-9a-fA-F]{8}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{12}$"
                )
                relation_values = [v.strip() for v in str(value).split(",") if v.strip()]
                relation_ids = [v for v in relation_values if uuid_regex.match(v)]
                if relation_values and not relation_ids:
                    error_message = f"Invalid relation id(s) provided for property {prop_name}: {value}"
                    raise ValueError(error_message)
                return {"relation": [{"id": rid} for rid in relation_ids]}

            elif prop_type == "status":
                if not value:
                    return {"status": None}
                return {"status": {"name": str(value)}}

            elif prop_type == "people":
                # Handle people type - this requires user IDs
                import re

                uuid_regex = re.compile(
                    r"^[0-9a-fA-F]{8}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{12}$"
                )
                # Check if value looks like UUID
                if not value:
                    return {"people": []}

                people_values = [v.strip() for v in str(value).split(",") if v.strip()]
                # Use a differently named variable to avoid redefinition issues
                people_id_objects: list[dict[str, str]] = []

                for person_value in people_values:
                    if uuid_regex.match(person_value):
                        # It's a user ID - create a dictionary with the ID
                        people_id_objects.append({"id": person_value})
                    else:
                        # For non-UUID values, log a warning
                        self.log(
                            f"Warning: '{person_value}' doesn't appear to be a valid user ID. "
                            f"People properties require Notion user IDs, not names."
                        )

                return {"people": people_id_objects}

            elif prop_type == "formula":
                # Formula properties are calculated by Notion and cannot be set
                self.log(f"Skipping formula property {prop_name} as it cannot be set manually")
                return {}  # Return empty dict instead of None

            elif prop_type == "rollup":
                # Rollup properties are calculated by Notion and cannot be set
                self.log(f"Skipping rollup property {prop_name} as it cannot be set manually")
                return {}  # Return empty dict instead of None

            elif prop_type in {"created_by", "last_edited_by", "created_time", "last_edited_time"}:
                # These are system properties and cannot be set
                self.log(f"Skipping system property {prop_name} as it cannot be set manually")
                return {}  # Return empty dict instead of None

            else:
                # Log unknown property type
                self.log(
                    f"Unknown property type '{prop_type}' for property '{prop_name}'. "
                    f"Please check your Notion database schema."
                )
                return {}  # Return empty dict instead of None

        except (ValueError, TypeError) as e:
            self.log(f"Error formatting property {prop_name}: {e!s}")
            # Returns empty value or None based on type
            empty_values: dict[str, dict[str, Any]] = {
                "title": {"title": []},
                "rich_text": {"rich_text": []},
                "select": {"select": None},
                "multi_select": {"multi_select": []},
                "date": {"date": None},
                "number": {"number": None},
                "checkbox": {"checkbox": False},
                "url": {"url": None},
                "email": {"email": None},
                "phone_number": {"phone_number": None},
                "files": {"files": []},
                "status": {"status": None},
                "people": {"people": []},
                "relation": {"relation": []},
            }
            return empty_values.get(prop_type, {}) if prop_type in empty_values else {"value": None}

    def create_page_as_dataframe(self) -> DataFrame:
        """Create a new page in a Notion database and return as DataFrame."""
        page_response = self._create_notion_page()

        # If error, return DataFrame with error information
        if "error" in page_response:
            error_df = pd.DataFrame({"error": [page_response["error"]]})
            return DataFrame(error_df)

        # Extract the important information from the page response
        page_data = {
            "page_id": [page_response.get("id", "")],
            "url": [page_response.get("url", "")],
            "created_time": [page_response.get("created_time", "")],
            "last_edited_time": [page_response.get("last_edited_time", "")],
        }

        # Extract property values in a user-friendly format
        properties = page_response.get("properties", {})
        for prop_name, prop_content in properties.items():
            prop_type = next(iter(prop_content)) if prop_content else ""

            # Format the property based on its type
            if prop_type == "title" and prop_content.get("title"):
                text_content = []
                text_content = [
                    item["text"]["content"]
                    for item in prop_content.get("title", [])
                    if item.get("type") == "text" and item.get("text", {}).get("content")
                ]
                page_data[f"{prop_name}"] = [" ".join(text_content) if text_content else ""]

            elif prop_type == "rich_text" and prop_content.get("rich_text"):
                text_content = []
                text_content = [
                    item["text"]["content"]
                    for item in prop_content.get("rich_text", [])
                    if item.get("type") == "text" and "text" in item and "content" in item["text"]
                ]
                page_data[f"{prop_name}"] = [" ".join(text_content) if text_content else ""]

            elif prop_type == "select" and prop_content.get("select"):
                page_data[f"{prop_name}"] = [prop_content["select"].get("name", "")]

            elif prop_type == "multi_select" and prop_content.get("multi_select"):
                multi_select_values = [item.get("name", "") for item in prop_content.get("multi_select", [])]
                page_data[f"{prop_name}"] = [", ".join(multi_select_values)]

            elif prop_type == "date" and prop_content.get("date"):
                date_info = prop_content["date"]
                date_value = date_info.get("start", "")
                if date_info.get("end"):
                    date_value += f" to {date_info['end']}"
                page_data[f"{prop_name}"] = [date_value]

            elif prop_type == "checkbox":
                page_data[f"{prop_name}"] = [str(prop_content.get("checkbox", False))]

            elif prop_type in ["number", "url", "email", "phone_number"]:
                page_data[f"{prop_name}"] = [str(prop_content.get(prop_type, ""))]

            elif prop_type == "status" and prop_content.get("status"):
                page_data[f"{prop_name}"] = [prop_content["status"].get("name", "")]

            elif prop_type == "relation":
                relation_ids = [item.get("id", "") for item in prop_content.get("relation", [])]
                page_data[f"{prop_name}"] = [", ".join(relation_ids)]

            # Add other property types as needed

        # Add database info and additional metadata
        page_data["database_id"] = [page_response.get("parent", {}).get("database_id", "")]
        page_data["database_name"] = [self.database_id.split(" (")[0] if "(" in self.database_id else self.database_id]
        page_data["created_by"] = [page_response.get("created_by", {}).get("id", "")]
        page_data["last_edited_by"] = [page_response.get("last_edited_by", {}).get("id", "")]

        # Add the full JSON response as a column for debugging/advanced use
        page_data["api_response"] = [json.dumps(page_response)]

        # Create DataFrame
        result_df = pd.DataFrame(page_data)

        # Order columns: metadata first, then properties
        metadata_cols = [
            "page_id",
            "database_id",
            "database_name",
            "url",
            "created_time",
            "last_edited_time",
            "created_by",
            "last_edited_by",
        ]
        property_cols = [col for col in result_df.columns if col not in metadata_cols and col != "api_response"]

        # Put api_response at the end
        ordered_cols = metadata_cols + sorted(property_cols) + ["api_response"]

        # Filter out columns that don't exist in the dataframe
        existing_cols = [col for col in ordered_cols if col in result_df.columns]

        return DataFrame(result_df[existing_cols])

    def _create_notion_page(self) -> dict[str, Any]:
        """Internal method to create the Notion page and return the API response."""
        if not self.database_id or self.database_id == "Loading databases...":
            return {"error": "Please select a valid database first."}

        # Debug logs
        self.log(f"Creating page in database: {self.database_id}")
        self.log(f"Available properties: {self._database_properties}")

        # Ensure we have database properties
        if not self._database_properties:
            self._database_properties = self.fetch_database_properties(self.database_id)
            self.log(f"Fetched properties: {self._database_properties}")

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        # Find title property
        title_property = None
        for prop_name, prop_info in self._database_properties.items():
            if prop_info["type"] == "title":
                title_property = prop_name
                self.log(f"Found title property: {title_property}")
                break

        properties: dict[str, Any] = {}
        num_properties = getattr(self, "number_of_properties", 0)
        self.log(f"Processing {num_properties} properties")

        for i in range(1, num_properties + 1):
            property_name = getattr(self, f"property_{i}_name", None)
            property_value = getattr(self, f"property_{i}_value", None)

            self.log(f"Processing property {i}:")
            self.log(f"Name: {property_name}")
            self.log(f"Value: {property_value}")

            # Skip if no property name
            if not property_name:
                self.log("No property name provided, skipping")
                continue

            # Get property info
            prop_info = self._database_properties.get(property_name)
            if not prop_info:
                self.log(f"Property {property_name} not found in database properties")
                continue

            self.log(f"Property info: {prop_info}")

            # Get detailed info about this property type
            prop_type = prop_info["type"]
            self.log(f"Property type: {prop_type}")

            # Skip system properties that can't be set
            if prop_type in ["formula", "rollup", "created_by", "last_edited_by", "created_time", "last_edited_time"]:
                self.log(f"Skipping system/computed property {property_name} of type {prop_type}")
                continue

            # Format the value
            formatted_value = self.format_property_value(
                property_name, prop_info, property_value if property_value else ""
            )

            self.log(f"Formatted value: {formatted_value}")

            # Add to properties if we got a valid formatted value
            if formatted_value is not None:
                properties[property_name] = formatted_value
                self.log(f"Added property {property_name}")

            # Check if this is the title property
            if prop_type == "title":
                title_property = None  # We already have a title set

        # Add default title if needed
        if title_property:
            self.log("Adding default title property")
            properties[title_property] = {"title": [{"type": "text", "text": {"content": "New Page"}}]}

        # Final check
        if not properties:
            self.log("No properties were created!")
            return {"error": "No valid properties defined. Please check the logs for details."}

        # Create page data
        # Extract the pure database ID before sending to the API
        clean_db_id = self.database_id.split("(")[-1].rstrip(")") if "(" in self.database_id else self.database_id
        data = {"parent": {"database_id": clean_db_id}, "properties": properties}

        self.log(f"Final request data: {json.dumps(data, indent=2)}")

        # Send request
        try:
            response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data, timeout=10)

            self.log(f"Response status: {response.status_code}")
            self.log(f"Response body: {response.text}")

            if not response.ok:
                error_msg = (
                    f"Notion API error: {response.status_code}\n"
                    f"Response: {response.text}\n"
                    f"Request data: {json.dumps(data, indent=2)}"
                )
                self.log(error_msg)
                return {"error": error_msg}

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Error creating page: {e!s}"
            self.log(error_msg)
            return {"error": error_msg}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                databases = self.fetch_databases()
                # Format options as "Name (ID)"
                formatted_dbs: list[str] = []
                for db in databases:
                    db_name = db.get("title", [{}])[0].get("text", {}).get("content", "Untitled")
                    db_id = db["id"]
                    formatted_name = f"{db_name} ({db_id})"
                    formatted_dbs.append(formatted_name)

                build_config["database_id"]["options"] = formatted_dbs
                if databases:
                    build_config["database_id"]["value"] = formatted_dbs[0]

                # Skip setting tooltips to avoid any type errors

            # When database_id changes
            if field_name == "database_id":
                # Only show number_of_properties and enable it if a valid database is selected
                if field_value and field_value != "Loading databases...":
                    build_config["number_of_properties"]["advanced"] = False
                    # Reset number of properties to 0 when database changes
                    build_config["number_of_properties"]["value"] = 0
                    # Store database properties globally
                    self._database_properties = self.fetch_database_properties(field_value)
                else:
                    build_config["number_of_properties"]["advanced"] = True
                    build_config["number_of_properties"]["value"] = 0
                    self._database_properties = {}

            # When number_of_properties changes
            if field_name == "number_of_properties":
                try:
                    num_properties = int(field_value)
                except ValueError:
                    self.log("Invalid number of properties")
                    return build_config

                # Validate number of properties
                if num_properties > self.MAX_PROPERTIES:
                    num_properties = self.MAX_PROPERTIES
                    build_config["number_of_properties"]["value"] = self.MAX_PROPERTIES

                # Default keys that should not be removed
                default_keys = {"code", "_type", "notion_secret", "database_id", "number_of_properties"}

                # Clear existing property fields
                for key in list(build_config.keys()):
                    if key not in default_keys:
                        build_config.pop(key)

                # Get properties from database
                if not self._database_properties:
                    self._database_properties = self.fetch_database_properties(self.database_id)

                property_options = list(self._database_properties.keys())

                if not property_options:
                    property_options = ["No properties available"]

                # Create fields for each property
                for i in range(1, num_properties + 1):
                    name_key = f"property_{i}_name"
                    value_key = f"property_{i}_value"

                    # Add the property name dropdown
                    build_config[name_key] = DropdownInput(
                        name=name_key,
                        display_name=f"Property {i} - Name",
                        info="Select the property name",
                        options=property_options,
                        value=property_options[0] if property_options else "",
                    ).to_dict()

                    # Get property type info
                    prop_type = "text"
                    info_text = "Enter the value for this property"

                    if property_options and property_options[0] != "No properties available":
                        first_prop = self._database_properties[property_options[0]]
                        prop_type = first_prop["type"]
                        info_text = f"Enter the value for this property (type: {prop_type})"

                        if prop_type in ["select", "multi_select", "status"]:
                            options = first_prop.get(prop_type, {}).get("options", [])
                            option_names = [opt["name"] for opt in options]
                            info_text += f"\nValid options: {', '.join(option_names)}"
                            if prop_type == "multi_select":
                                info_text += "\nFor multiple values, separate with commas"

                        elif prop_type == "people":
                            info_text = (
                                "Enter Notion user IDs (not names) for people. Separate multiple IDs with commas."
                            )

                        elif prop_type == "relation":
                            info_text = "Enter page IDs to link to. Separate multiple IDs with commas."

                        elif prop_type in [
                            "formula",
                            "rollup",
                            "created_by",
                            "last_edited_by",
                            "created_time",
                            "last_edited_time",
                        ]:
                            info_text = "This property is computed by Notion and cannot be set manually."

                    # Add the value input field
                    build_config[value_key] = MessageTextInput(
                        name=value_key,
                        display_name=f"Property {i} - Value",
                        info=info_text,
                        placeholder=f"Enter {prop_type} value...",
                    ).to_dict()

                build_config["number_of_properties"]["value"] = num_properties

        except (ValueError, KeyError) as e:
            self.log(f"Error updating build config: {e!s}")

            build_config["database_id"]["options"] = ["Error loading databases"]
            build_config["database_id"]["value"] = "Error loading databases"
            build_config["number_of_properties"]["advanced"] = True
            build_config["number_of_properties"]["value"] = 0

        return build_config
