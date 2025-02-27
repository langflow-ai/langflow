import json
from typing import Any, cast

import requests

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput
from langflow.io import Output
from langflow.schema import Data, dotdict


class NotionPageUpdate(Component):
    """A component that updates properties of a Notion page with database-based page selection."""

    display_name: str = "Update Page Property"
    description: str = "Update properties of a Notion page by first selecting a database and then a page."
    documentation: str = "https://docs.langflow.org/integrations/notion/page-update"
    icon: str = "NotionDirectoryLoader"

    MAX_PROPERTIES = 10

    _page_properties: dict[str, Any] = {}
    _database_pages_cache: dict[str, list[dict[str, Any]]] = {}

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
            info="Select a database to list its pages",
            options=["Loading databases..."],
            value="Loading databases...",
            real_time_refresh=True,
            required=True,
        ),
        DropdownInput(
            name="page_id",
            display_name="Page",
            info="Select a page to update",
            options=["Select a database first..."],
            value="Select a database first...",
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
                title = "Untitled Database"
                if "title" in db:
                    title_parts = db.get("title", [])
                    if title_parts:
                        title = "".join(part.get("plain_text", "") for part in title_parts)

                databases.append({"id": db["id"], "title": title or "Untitled Database"})

            return sorted(databases, key=lambda x: x["title"].lower())

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching databases: {e!s}")
            return []

    def fetch_database_pages(self, database_id: str) -> list[dict[str, Any]]:
        """Fetch pages from a specific database."""
        if "(" in database_id and database_id.endswith(")"):
            database_id = database_id.split("(")[-1].rstrip(")")

        if not database_id or database_id in ["Loading databases...", "No databases found"]:
            return []

        if database_id in self._database_pages_cache:
            return self._database_pages_cache[database_id]

        headers = {
            "Authorization": f"Bearer {self.notion_secret}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = requests.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=headers,
                json={"page_size": 100},
                timeout=15,
            )
            response.raise_for_status()

            pages = []
            for page in response.json().get("results", []):
                title = "Untitled Page"
                if "properties" in page:
                    for prop_value in page["properties"].values():
                        if prop_value.get("type") == "title":
                            title_parts = prop_value.get("title", [])
                            if title_parts:
                                title = "".join(part.get("plain_text", "") for part in title_parts)
                                break

                pages.append({"id": page["id"], "title": title, "last_edited_time": page.get("last_edited_time", "")})

            pages_sorted = sorted(pages, key=lambda x: x["title"].lower())
            self._database_pages_cache[database_id] = pages_sorted

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching pages from database: {e!s}")
            return []
        else:
            return pages_sorted

    def fetch_page_properties(self) -> dict[str, Any]:
        """Fetch the current properties of the page."""
        if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
            return {}

        actual_page_id = self.get_actual_page_id()
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
            if field_name is None or field_name == "notion_secret":
                databases = self.fetch_databases()
                options = [f"{db['title']} ({db['id']})" for db in databases]

                if not options:
                    options = ["No databases found"]

                build_config["database_id"]["options"] = options
                if options and options[0] != "No databases found":
                    build_config["database_id"]["value"] = options[0]

                build_config["page_id"]["options"] = ["Select a database first..."]
                build_config["page_id"]["value"] = "Select a database first..."
                build_config["number_of_properties"]["value"] = 0

            if field_name == "database_id":
                if field_value and field_value not in ["Loading databases...", "No databases found"]:
                    pages = self.fetch_database_pages(field_value)
                    page_options = [f"{page['title']} ({page['id']})" for page in pages]

                    if not page_options:
                        page_options = ["No pages found"]

                    build_config["page_id"]["options"] = page_options
                    if page_options and page_options[0] != "No pages found":
                        build_config["page_id"]["value"] = page_options[0]
                    else:
                        build_config["page_id"]["value"] = "No pages found"

                    build_config["number_of_properties"]["value"] = 0
                    self._page_properties = {}
                else:
                    build_config["page_id"]["options"] = ["Select a database first..."]
                    build_config["page_id"]["value"] = "Select a database first..."
                    build_config["number_of_properties"]["value"] = 0
                    self._page_properties = {}

            if field_name == "page_id":
                if field_value and field_value not in ["Select a database first...", "No pages found"]:
                    build_config["number_of_properties"]["value"] = 0
                    self._page_properties = self.fetch_page_properties()
                else:
                    build_config["number_of_properties"]["value"] = 0
                    self._page_properties = {}

            if field_name == "number_of_properties":
                try:
                    num_properties = int(field_value)
                except ValueError:
                    self.log("Invalid number of properties")
                    return build_config

                if num_properties > self.MAX_PROPERTIES:
                    num_properties = self.MAX_PROPERTIES
                    build_config["number_of_properties"]["value"] = self.MAX_PROPERTIES

                default_keys = {"code", "_type", "notion_secret", "database_id", "page_id", "number_of_properties"}
                for key in list(build_config.keys()):
                    if key not in default_keys:
                        build_config.pop(key)

                if not self._page_properties:
                    self._page_properties = self.fetch_page_properties()

                property_options = list(self._page_properties.keys())
                if not property_options:
                    property_options = ["No properties available"]

                for i in range(1, num_properties + 1):
                    name_key = f"property_{i}_name"
                    value_key = f"property_{i}_value"

                    build_config[name_key] = DropdownInput(
                        name=name_key,
                        display_name=f"Property {i} - Name",
                        info="Select the property to update",
                        options=property_options,
                        value=property_options[0] if property_options else "",
                    ).to_dict()

                    prop_type = "text"
                    info_text = "Enter the new value for this property"
                    if property_options and property_options[0] != "No properties available":
                        prop_info = self._page_properties[property_options[0]]
                        prop_type = prop_info["type"]
                        info_text = f"Enter the new value for this property (type: {prop_type})"
                        if prop_type in ["select", "multi_select", "status"]:
                            options_list: list[dict[str, Any]] = prop_info.get(prop_type, {}).get("options", [])
                            option_names = [opt["name"] for opt in options_list]
                            info_text += f"\nValid options: {', '.join(option_names)}"
                            if prop_type == "multi_select":
                                info_text += "\nFor multiple values, separate with commas"

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

    def get_actual_page_id(self) -> str:
        """Extract the actual page ID from the format 'Title (ID)'."""
        if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
            return ""

        if "(" in self.page_id and self.page_id.endswith(")"):
            return self.page_id.split("(")[-1].rstrip(")")

        return self.page_id

    def update_page(self) -> Data:
        """Update properties of a Notion page."""
        if not self.page_id or self.page_id in ["Select a database first...", "No pages found"]:
            return Data(data={"error": "Please select a valid page"})

        actual_page_id = self.get_actual_page_id()
        if not actual_page_id:
            return Data(data={"error": "Invalid page ID format"})

        self.log(f"Updating page: {actual_page_id}")
        self.log(f"Available properties: {self._page_properties}")

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

            if not property_name:
                self.log("No property name provided, skipping")
                continue

            prop_info = self._page_properties.get(property_name)
            if not prop_info:
                self.log(f"Property {property_name} not found in page properties")
                continue

            self.log(f"Property info: {prop_info}")

            formatted_value = self.format_property_value(
                property_name, prop_info, property_value if property_value else ""
            )

            self.log(f"Formatted value: {formatted_value}")

            if formatted_value:
                properties[property_name] = formatted_value
                self.log(f"Added property {property_name}")

        if not properties:
            self.log("No properties were updated!")
            return Data(data={"error": "No valid properties defined. Please check the logs for details."})

        data = {"properties": properties}

        self.log(f"Final request data: {json.dumps(data, indent=2)}")

        try:
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

            response_data = response.json()
            if self.page_id and "(" in self.page_id:
                page_title = self.page_id.split(" (")[0]
                response_data["page_title"] = page_title

            return Data(data=cast(dict[str, Any], response_data))

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
                    url_parts = value.split("/")
                    file_name = url_parts[-1]
                    return {"files": [{"name": file_name, "type": "external", "external": {"url": value}}]}
                return {"files": []}

            if prop_type == "status":
                return {"status": {"name": str(value)}}

            self.log(f"Unknown property type {prop_type}, defaulting to rich_text")
            return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

        except (ValueError, TypeError) as e:
            self.log(f"Error formatting property {prop_name}: {e}")
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
            result: dict[str, Any] = empty_values.get(prop_type, {"rich_text": []})
            return result
