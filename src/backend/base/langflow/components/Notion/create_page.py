import json
from typing import Any

import requests

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict


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
            display_name="Database",
            info="Select a database",
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
        Output(name="data", display_name="Page Data", method="create_page"),
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
                # Select should be a single object, not an array
                return {"select": {"name": str(value)}}

            if prop_type == "multi_select":
                # Multi-select is an array of objects with "name"
                values = [v.strip() for v in str(value).split(",")]
                return {"multi_select": [{"name": v} for v in values if v]}

            if prop_type == "date":
                # Tries to interpret if it is a date range
                if " to " in value:
                    start, end = value.split(" to ")
                    return {"date": {"start": start.strip(), "end": end.strip()}}
                return {"date": {"start": str(value)}}

            if prop_type == "number":
                try:
                    # Converts to float to accept decimals
                    return {"number": float(value)}
                except ValueError:
                    return {"number": 0}

            elif prop_type == "checkbox":
                return {"checkbox": str(value).lower() in ("true", "1", "yes", "y", "on")}

            elif prop_type == "url":
                return {"url": str(value)}

            elif prop_type == "email":
                return {"email": str(value)}

            elif prop_type == "phone_number":
                return {"phone_number": str(value)}

            elif prop_type == "files":
                # If it is a URL, create as external file
                if value.startswith(("http://", "https://")):
                    return {"files": [{"name": value.split("/")[-1], "type": "external", "external": {"url": value}}]}
                return {"files": []}

            elif prop_type == "status":
                return {"status": {"name": str(value)}}

            else:
                # For unknown types, use rich_text
                self.log(f"Unknown property type {prop_type}, defaulting to rich_text")
                return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

        except (ValueError, TypeError) as e:
            self.log(f"Error formatting property {prop_name}: {e!s}")
            # Returns empty value appropriate for the type
            empty_values: dict[str, dict[str, Any]] = {
                "title": {"title": []},
                "rich_text": {"rich_text": []},
                "select": {"select": None},
                "multi_select": {"multi_select": []},
                "date": {"date": None},
                "number": {"number": 0},
                "checkbox": {"checkbox": False},
                "url": {"url": ""},
                "email": {"email": ""},
                "phone_number": {"phone_number": ""},
                "files": {"files": []},
                "status": {"status": None},
            }
            default_value: dict[str, Any] = {"rich_text": []}
            return empty_values.get(prop_type, default_value)

    def create_page(self) -> Data:
        """Create a new page in a Notion database."""
        if not self.database_id or self.database_id == "Loading databases...":
            return Data(data={"error": "Please select a valid database first."})

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

        properties = {}
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

            # Format the value
            formatted_value = self.format_property_value(
                property_name, prop_info, property_value if property_value else ""
            )

            self.log(f"Formatted value: {formatted_value}")

            # Add to properties
            if formatted_value:
                properties[property_name] = formatted_value
                self.log(f"Added property {property_name}")

            # Check if this is the title property
            if prop_info["type"] == "title":
                title_property = None  # We already have a title set

        # Add default title if needed
        if title_property:
            self.log("Adding default title property")
            properties[title_property] = {"title": [{"type": "text", "text": {"content": "New Page"}}]}

        # Final check
        if not properties:
            self.log("No properties were created!")
            return Data(data={"error": "No valid properties defined. Please check the logs for details."})

        # Create page data
        data = {"parent": {"database_id": self.database_id}, "properties": properties}

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
                return Data(data={"error": error_msg})

            response.raise_for_status()
            return Data(data={"page": response.json()})
        except requests.exceptions.RequestException as e:
            error_msg = f"Error creating page: {e!s}"
            self.log(error_msg)
            return Data(data={"error": error_msg})

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                databases = self.fetch_databases()
                build_config["database_id"]["options"] = [db["id"] for db in databases]
                if databases:
                    build_config["database_id"]["value"] = databases[0]["id"]

                # Add tooltips with database titles
                tooltips = {
                    db["id"]: db.get("title", [{}])[0].get("text", {}).get("content", "Untitled") for db in databases
                }
                build_config["database_id"]["tooltips"] = tooltips

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
