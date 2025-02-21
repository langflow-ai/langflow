import json
from typing import Any, cast

import requests

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict


class NotionPageUpdate(Component):
    """A component that updates properties of a Notion page with dynamic property selection."""

    display_name: str = "Update Page Property"
    description: str = "Update the properties of a Notion page with dynamic property selection."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-update"
    icon: str = "NotionDirectoryLoader"

    # Maximum number of properties that can be updated at once
    MAX_PROPERTIES = 10

    # Store page properties globally
    _page_properties: dict[str, Any] = {}

    inputs = [
        SecretStrInput(
            name="notion_secret",
            display_name="Notion Secret",
            info="The Notion integration token.",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="page_id",
            display_name="Page",
            info="Select a page to update",
            options=["Loading pages..."],
            value="Loading pages...",
            real_time_refresh=True,
            required=True,
        ),
        IntInput(
            name="number_of_properties",
            display_name="Number of Properties",
            info="Number of properties to update",
            value=0,
            real_time_refresh=True,
            range_spec=RangeSpec(min=0, max=MAX_PROPERTIES, step=1, step_type="int"),
        ),
    ]

    outputs = [
        Output(name="data", display_name="Updated Page", method="update_page"),
    ]

    def fetch_pages(self) -> list[dict[str, Any]]:
        """Fetch available pages from Notion API."""
        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={"filter": {"value": "page", "property": "object"}},
                timeout=10,
            )
            response.raise_for_status()

            pages = []
            for page in response.json().get("results", []):
                # Get the page title from properties
                title = "Untitled Page"
                if "properties" in page:
                    # Look for title property
                    title_prop = page["properties"].get("title", page["properties"].get("Name", {}))
                    if title_prop and "title" in title_prop:
                        title_parts = title_prop.get("title", [])
                        if title_parts:
                            title = "".join(part.get("plain_text", "") for part in title_parts)

                pages.append({"id": page["id"], "title": title or "Untitled Page"})

            return sorted(pages, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pages: {e!s}")
            return []

    def fetch_page_properties(self) -> dict[str, Any]:
        """Fetch the current properties of the page."""
        if not self.page_id or self.page_id == "Loading pages...":
            return {}

        # Get the actual page ID from the title
        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)

        if not actual_page_id:
            return {}

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = requests.get(f"https://api.notion.com/v1/pages/{actual_page_id}", headers=headers, timeout=10)
            response.raise_for_status()
            return response.json().get("properties", {})
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching page properties: {e}")
            return {}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update build configuration based on field updates."""
        try:
            # When notion_secret is updated or initially loaded
            if field_name is None or field_name == "notion_secret":
                # Fetch the pages
                pages = self.fetch_pages()

                # Prepare the dropdown options using the titles
                options = [page["title"] for page in pages]

                build_config["page_id"]["options"] = options
                if options:
                    build_config["page_id"]["value"] = options[0]

                # Add tooltips with page IDs
                tooltips = {page["title"]: page["id"] for page in pages}
                build_config["page_id"]["tooltips"] = tooltips

            # When page_id changes
            if field_name == "page_id":
                if field_value and field_value != "Loading pages...":
                    # Reset number of properties to 0 when page changes
                    build_config["number_of_properties"]["value"] = 0
                    # Store page properties globally
                    self._page_properties = self.fetch_page_properties()
                else:
                    build_config["number_of_properties"]["value"] = 0
                    self._page_properties = {}

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
                default_keys = {"code", "_type", "notion_secret", "page_id", "number_of_properties"}

                # Clear existing property fields
                for key in list(build_config.keys()):
                    if key not in default_keys:
                        build_config.pop(key)

                # Get properties from page
                if not self._page_properties:
                    self._page_properties = self.fetch_page_properties()

                property_options = list(self._page_properties.keys())

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
                        info="Select the property to update",
                        options=property_options,
                        value=property_options[0] if property_options else "",
                    ).to_dict()

                    # Get property type info
                    prop_type = "text"
                    info_text = "Enter the new value for this property"

                    if property_options and property_options[0] != "No properties available":
                        prop_info = self._page_properties[property_options[0]]
                        prop_type = prop_info["type"]
                        info_text = f"Enter the new value for this property (type: {prop_type})"

                        if prop_type in ["select", "multi_select", "status"]:
                            options = prop_info.get(prop_type, {}).get("options", [])
                            option_names = [opt["name"] for opt in options]
                            info_text += f"\nValid options: {', '.join(option_names)}"
                            if prop_type == "multi_select":
                                info_text += "\nFor multiple values, separate with commas"

                    # Add the value input field
                    build_config[value_key] = MessageTextInput(
                        name=value_key,
                        display_name=f"Property {i} - Value",
                        info=info_text,
                        placeholder=f"Enter new {prop_type} value...",
                    ).to_dict()

                build_config["number_of_properties"]["value"] = num_properties

        except KeyError as e:
            self.log(f"Error updating build config: {e}")
            build_config["number_of_properties"]["advanced"] = True
            build_config["number_of_properties"]["value"] = 0

        return build_config

    def update_page(self) -> Data:
        """Update properties of a Notion page."""
        if not self.page_id or self.page_id == "Loading pages...":
            return Data(data={"error": "Please select a valid page"})

        # Get the actual page ID from the title
        pages = self.fetch_pages()
        title_to_id = {page["title"]: page["id"] for page in pages}
        actual_page_id = title_to_id.get(self.page_id)

        if not actual_page_id:
            return Data(data={"error": "Page not found"})

        # Debug logs
        self.log(f"Updating page: {actual_page_id}")
        self.log(f"Available properties: {self._page_properties}")

        # Ensure we have page properties
        if not self._page_properties:
            self._page_properties = self.fetch_page_properties()
            self.log(f"Fetched properties: {self._page_properties}")

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

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
            prop_info = self._page_properties.get(property_name)
            if not prop_info:
                self.log(f"Property {property_name} not found in page properties")
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

        # Final check
        if not properties:
            self.log("No properties were updated!")
            return Data(data={"error": "No valid properties defined. Please check the logs for details."})

        # Create update data
        data = {"properties": properties}

        self.log(f"Final request data: {json.dumps(data, indent=2)}")

        try:
            # Send update request
            response = requests.patch(
                f"https://api.notion.com/v1/pages/{actual_page_id}", headers=headers, json=data, timeout=10
            )

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
            return Data(data=cast(dict[str, Any], response.json()))

        except requests.exceptions.RequestException as e:
            error_msg = f"Error updating page: {e}"
            self.log(error_msg)
            return Data(data={"error": error_msg})

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
                return {"select": {"name": str(value)}}

            if prop_type == "multi_select":
                values = [v.strip() for v in str(value).split(",")]
                return {"multi_select": [{"name": v} for v in values if v]}

            if prop_type == "date":
                if " to " in value:
                    start, end = value.split(" to ")
                    return {"date": {"start": start.strip(), "end": end.strip()}}
                return {"date": {"start": str(value)}}

            if prop_type == "number":
                try:
                    return {"number": float(value)}
                except ValueError:
                    return {"number": 0}

            if prop_type == "checkbox":
                return {"checkbox": str(value).lower() in ("true", "1", "yes", "y", "on")}

            if prop_type == "url":
                return {"url": str(value)}

            if prop_type == "email":
                return {"email": str(value)}

            if prop_type == "phone_number":
                return {"phone_number": str(value)}

            if prop_type == "files":
                if value.startswith(("http://", "https://")):
                    return {"files": [{"name": value.split("/")[-1], "type": "external", "external": {"url": value}}]}
                return {"files": []}

            if prop_type == "status":
                return {"status": {"name": str(value)}}

            # For unknown types, use rich_text
            self.log(f"Unknown property type {prop_type}, defaulting to rich_text")
            return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

        except (ValueError, TypeError) as e:
            self.log(f"Error formatting property {prop_name}: {e}")
            # Return empty value appropriate for the type
            empty_values = {
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
            return empty_values.get(prop_type, {"rich_text": []})
