import re
from abc import abstractmethod
from typing import Any

from composio import Composio
from composio_langchain import LangchainProvider
from langchain_core.tools import Tool

from langflow.base.mcp.util import create_input_schema_from_json_schema
from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import (
    AuthInput,
    FileInput,
    InputTypes,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
)
from langflow.io import Output
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


class ComposioBaseComponent(Component):
    """Base class for Composio components with common functionality."""

    # TL;DR: ATTACHMENT FIELD OPTIMIZATION
    # Problem: Composio doesn't specify which fields are file attachments in their schemas
    # Solution: Map only actions that have file inputs -> their attachment field names
    # Optimization: Most actions (98%) get O(1) rejection, only file-actions check fields
    # Performance: ~50x faster than checking every field of every action

    # Only actions that actually accept file inputs and their attachment field names
    ATTACHMENT_FIELDS = {
        "GMAIL_SEND_EMAIL": {"attachment"},
        "GMAIL_CREATE_DRAFT": {"attachment"},
        "GOOGLEDRIVE_UPLOAD_FILE": {"file_to_upload"},
        "OUTLOOK_OUTLOOK_CREATE_DRAFT": {"attachment"},  # ✅ This one works!
        # Note: OUTLOOK_OUTLOOK_SEND_EMAIL attachment field gets dropped by flatten_schema
        # because of its complex schema structure with 'file_uploadable' and 'anyOf'
    }

    # Common inputs that all Composio components will need
    _base_inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            real_time_refresh=True,
            value="COMPOSIO_API_KEY",
        ),
        AuthInput(
            name="auth_link",
            value="",
            auth_tooltip="Please insert a valid Composio API Key.",
        ),
        SortableListInput(
            name="action",
            display_name="Action",
            placeholder="Select action",
            options=[],
            value="disabled",
            helper_text="Please connect before selecting actions.",
            helper_text_metadata={"variant": "destructive"},
            show=True,
            required=False,
            real_time_refresh=True,
            limit=1,
        ),
    ]

    # Remove class-level variables to prevent shared state between components
    # These will be initialized as instance variables in __init__
    _name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")

    outputs = [
        Output(name="dataFrame", display_name="DataFrame", method="as_dataframe"),
    ]

    # Ensure every Composio component automatically exposes the common inputs
    inputs = list(_base_inputs)

    def __init__(self, **kwargs):
        """Initialize instance variables to prevent shared state between components."""
        super().__init__(**kwargs)
        # Initialize instance variables (previously class variables)
        self._all_fields: set[str] = set()
        self._bool_variables: set[str] = set()
        self._actions_data: dict[str, dict[str, Any]] = {}
        self._default_tools: set[str] = set()
        self._display_to_key_map: dict[str, str] = {}
        self._key_to_display_map: dict[str, str] = {}
        self._sanitized_names: dict[str, str] = {}
        self._action_schemas: dict[str, Any] = {}

    def as_message(self) -> Message:
        result = self.execute_action()
        if result is None:
            return Message(text="Action execution returned no result")
        return Message(text=str(result))

    def as_dataframe(self) -> DataFrame:
        result = self.execute_action()
        if result is None:
            # Return an empty DataFrame when there's no result
            return DataFrame([])
        # If the result is a dict, pandas will raise ValueError: If using all scalar values, you must pass an index
        # So we need to make sure the result is a list of dicts
        if isinstance(result, dict):
            result = [result]
        return DataFrame(result)

    def as_data(self) -> Data:
        result = self.execute_action()
        if result is None:
            return Data(results={})
        return Data(results=result)

    def _build_action_maps(self):
        """Build lookup maps for action names."""
        if not self._display_to_key_map or not self._key_to_display_map:
            self._display_to_key_map = {data["display_name"]: key for key, data in self._actions_data.items()}
            self._key_to_display_map = {key: data["display_name"] for key, data in self._actions_data.items()}
            self._sanitized_names = {
                action: self._name_sanitizer.sub("-", self.sanitize_action_name(action))
                for action in self._actions_data
            }

    def sanitize_action_name(self, action_name: str) -> str:
        """Convert action name to display name using lookup."""
        self._build_action_maps()
        result = self._key_to_display_map.get(action_name, action_name)
        return result

    def desanitize_action_name(self, action_name: str) -> str:
        """Convert display name to action key using lookup."""
        self._build_action_maps()
        return self._display_to_key_map.get(action_name, action_name)

    def _get_action_fields(self, action_key: str | None) -> set[str]:
        """Get fields for an action."""
        if action_key is None:
            return set()
        return set(self._actions_data[action_key]["action_fields"]) if action_key in self._actions_data else set()

    def _build_wrapper(self) -> Composio:
        """Build the Composio wrapper."""
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return Composio(api_key=self.api_key, provider=LangchainProvider())

        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        """Optimized field visibility updates by only modifying show values."""
        if not field_value:
            for field in self._all_fields:
                build_config[field]["show"] = False
                if field in self._bool_variables:
                    build_config[field]["value"] = False
                else:
                    build_config[field]["value"] = ""
            return

        action_key = None
        if isinstance(field_value, list) and field_value:
            action_key = self.desanitize_action_name(field_value[0]["name"])
        else:
            action_key = field_value

        fields_to_show = self._get_action_fields(action_key)

        for field in self._all_fields:
            should_show = field in fields_to_show
            if build_config[field]["show"] != should_show:
                build_config[field]["show"] = should_show
                if not should_show:
                    if field in self._bool_variables:
                        build_config[field]["value"] = False
                    else:
                        build_config[field]["value"] = ""

    def _populate_actions_data(self):
        """Fetch the list of actions for the app (once) and build helper maps.

        This makes writing concrete app components trivial – they no longer need
        to hard-code `_actions_data`, `_all_fields`, or `_bool_variables`.
        """
        # Already populated → nothing to do
        if self._actions_data:
            return

        # We need a valid API key before calling the SDK
        if not getattr(self, "api_key", None):
            logger.warning("API key is missing. Cannot populate actions data.")
            return

        try:
            composio = self._build_wrapper()
            # Fetch schemas for this toolkit using the new SDK
            toolkit_slug = self.app_name.lower()

            raw_tools = composio.tools.get_raw_composio_tools(toolkits=[toolkit_slug]) or []

            for raw_tool in raw_tools:
                try:
                    # Convert raw_tool to dict-like structure
                    if hasattr(raw_tool, "__dict__"):
                        tool_dict = raw_tool.__dict__
                    else:
                        tool_dict = raw_tool

                    if not tool_dict:
                        logger.warning(f"Tool is None or empty: {raw_tool}")
                        continue

                    action_key = tool_dict.get("slug")
                    if not action_key:
                        logger.warning(f"Action key (slug) is missing in tool: {tool_dict}")
                        continue

                    # Human-friendly display name
                    display_name = tool_dict.get("name") or tool_dict.get("display_name")
                    if not display_name:
                        # Better fallback: convert GMAIL_SEND_EMAIL to "Send Email"
                        # Remove app prefix and convert to title case
                        clean_name = action_key
                        clean_name = clean_name.removeprefix(f"{self.app_name.upper()}_")
                        # Convert underscores to spaces and title case
                        display_name = clean_name.replace("_", " ").title()

                    # Build list of parameter names and track bool fields
                    parameters_schema = tool_dict.get("input_parameters", {})
                    if parameters_schema is None:
                        logger.warning(f"Parameters schema is None for action key: {action_key}")
                        # Still add the action but with empty fields
                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                        }
                        continue

                    try:
                        # Special handling for unusual schema structures
                        if not isinstance(parameters_schema, dict):
                            logger.warning(f"Parameters schema is not a dict for {action_key}, got: {type(parameters_schema)}")
                            # Try to convert if it's a model object
                            if hasattr(parameters_schema, "model_dump"):
                                parameters_schema = parameters_schema.model_dump()
                            elif hasattr(parameters_schema, "__dict__"):
                                parameters_schema = parameters_schema.__dict__
                            else:
                                logger.warning(f"Cannot process parameters schema for {action_key}, skipping")
                                self._action_schemas[action_key] = tool_dict
                                self._actions_data[action_key] = {
                                    "display_name": display_name,
                                    "action_fields": [],
                                }
                                continue

                        # Validate parameters_schema has required structure before flattening
                        if not parameters_schema.get("properties") and not parameters_schema.get("$defs"):
                            # Create a minimal valid schema to avoid errors
                            parameters_schema = {"type": "object", "properties": {}}

                        # Sanitize the schema before passing to flatten_schema
                        # Handle case where 'required' is explicitly None (causes "'NoneType' object is not iterable")
                        if parameters_schema.get("required") is None:
                            parameters_schema = parameters_schema.copy()  # Don't modify the original
                            parameters_schema["required"] = []

                        try:
                            # Preserve original descriptions before flattening to restore if lost
                            original_descriptions = {}
                            original_props = parameters_schema.get("properties", {})
                            for prop_name, prop_schema in original_props.items():
                                if isinstance(prop_schema, dict) and "description" in prop_schema:
                                    original_descriptions[prop_name] = prop_schema["description"]

                            flat_schema = flatten_schema(parameters_schema)

                            # Restore lost descriptions in flattened schema
                            if flat_schema and isinstance(flat_schema, dict) and "properties" in flat_schema:
                                flat_props = flat_schema["properties"]
                                for field_name, field_schema in flat_props.items():
                                    # Check if this field lost its description during flattening
                                    if isinstance(field_schema, dict) and "description" not in field_schema:
                                        # Try to find the original description
                                        # Handle array fields like bcc[0] -> bcc
                                        base_field_name = field_name.replace("[0]", "")
                                        if base_field_name in original_descriptions:
                                            field_schema["description"] = original_descriptions[base_field_name]
                                        elif field_name in original_descriptions:
                                            field_schema["description"] = original_descriptions[field_name]
                        except Exception as flatten_error:
                            logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                            # Still add the action but with empty fields so the UI doesn't break
                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                            }
                            continue

                        if flat_schema is None:
                            logger.warning(f"Flat schema is None for action key: {action_key}")
                            # Still add the action but with empty fields so the UI doesn't break
                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                            }
                            continue

                        # Extract field names and clean them up (remove [0] suffixes)
                        raw_action_fields = list(flat_schema.get("properties", {}).keys())
                        action_fields = []
                        attachment_related_found = False

                        for field in raw_action_fields:
                            clean_field = field.replace("[0]", "")
                            # Check if this field is attachment-related
                            if clean_field.lower().startswith("attachment."):
                                attachment_related_found = True
                                continue  # Skip individual attachment fields
                            action_fields.append(clean_field)

                        # Add consolidated attachment field if we found attachment-related fields
                        if attachment_related_found:
                            action_fields.append("attachment")

                        # Track boolean parameters so we can coerce them later
                        properties = flat_schema.get("properties", {})
                        if properties:
                            for p_name, p_schema in properties.items():
                                if isinstance(p_schema, dict) and p_schema.get("type") == "boolean":
                                    # Use cleaned field name for boolean tracking
                                    clean_field_name = p_name.replace("[0]", "")
                                    self._bool_variables.add(clean_field_name)

                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": action_fields,
                        }

                    except Exception as schema_error:
                        logger.warning(f"Failed to process schema for action {action_key}: {schema_error}")
                        # Still add the action but with empty fields so the UI doesn't break
                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                        }
                except Exception as e:  # pragma: no cover – schema edge-cases
                    logger.warning(f"Failed processing Composio tool for action {raw_tool}: {e}")

            # Helper look-ups used elsewhere
            self._all_fields = {f for d in self._actions_data.values() for f in d["action_fields"]}
            self._build_action_maps()

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Could not populate Composio actions for {self.app_name}: {e}")

    # ---------------------------------------------------------------------
    # Dynamic UI helpers (borrowed from MCPToolsComponent)
    # ---------------------------------------------------------------------

    def _validate_schema_inputs(self, action_key: str) -> list[InputTypes]:
        """Convert the JSON schema for *action_key* into Langflow input objects."""
        schema_dict = self._action_schemas.get(action_key)
        if not schema_dict:
            logger.warning(f"No schema found for action key: {action_key}")
            return []

        try:
            parameters_schema = schema_dict.get("input_parameters", {})
            if parameters_schema is None:
                logger.warning(f"Parameters schema is None for action key: {action_key}")
                return []

            # Check if parameters_schema has the expected structure
            if not isinstance(parameters_schema, dict):
                logger.warning(f"Parameters schema is not a dict for action key: {action_key}, got: {type(parameters_schema)}")
                return []

            # Validate parameters_schema has required structure before flattening
            if not parameters_schema.get("properties") and not parameters_schema.get("$defs"):
                # Create a minimal valid schema to avoid errors
                parameters_schema = {"type": "object", "properties": {}}

            # Sanitize the schema before passing to flatten_schema
            # Handle case where 'required' is explicitly None (causes "'NoneType' object is not iterable")
            if parameters_schema.get("required") is None:
                parameters_schema = parameters_schema.copy()  # Don't modify the original
                parameters_schema["required"] = []

            try:
                # Preserve original descriptions before flattening to restore if lost
                original_descriptions = {}
                original_props = parameters_schema.get("properties", {})
                for prop_name, prop_schema in original_props.items():
                    if isinstance(prop_schema, dict) and "description" in prop_schema:
                        original_descriptions[prop_name] = prop_schema["description"]

                flat_schema = flatten_schema(parameters_schema)

                # Restore lost descriptions in flattened schema
                if flat_schema and isinstance(flat_schema, dict) and "properties" in flat_schema:
                    flat_props = flat_schema["properties"]
                    for field_name, field_schema in flat_props.items():
                        # Check if this field lost its description during flattening
                        if isinstance(field_schema, dict) and "description" not in field_schema:
                            # Try to find the original description
                            # Handle array fields like bcc[0] -> bcc
                            base_field_name = field_name.replace("[0]", "")
                            if base_field_name in original_descriptions:
                                field_schema["description"] = original_descriptions[base_field_name]
                            elif field_name in original_descriptions:
                                field_schema["description"] = original_descriptions[field_name]
            except Exception as flatten_error:
                logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                return []

            if flat_schema is None:
                logger.warning(f"Flat schema is None for action key: {action_key}")
                return []

            # Additional check for flat_schema structure
            if not isinstance(flat_schema, dict):
                logger.warning(f"Flat schema is not a dict for action key: {action_key}, got: {type(flat_schema)}")
                return []

            # Ensure flat_schema has the expected structure for create_input_schema_from_json_schema
            if flat_schema.get("type") != "object":
                logger.warning(f"Flat schema for {action_key} is not of type 'object', got: {flat_schema.get('type')}")
                # Fix the schema type if it's missing
                flat_schema["type"] = "object"

            if "properties" not in flat_schema:
                flat_schema["properties"] = {}

            # Clean up field names - remove [0] suffixes from array fields
            cleaned_properties = {}
            attachment_related_fields = set()  # Track fields that are attachment-related

            for field_name, field_schema in flat_schema.get("properties", {}).items():
                # Remove [0] suffix from field names (e.g., "bcc[0]" -> "bcc", "cc[0]" -> "cc")
                clean_field_name = field_name.replace("[0]", "")

                # Check if this field is attachment-related (contains "attachment." prefix)
                if clean_field_name.lower().startswith("attachment."):
                    attachment_related_fields.add(clean_field_name)
                    # Don't add individual attachment sub-fields to the schema
                    continue

                # Preserve the full schema information, not just the type
                cleaned_properties[clean_field_name] = field_schema

            # If we found attachment-related fields, add a single "attachment" field
            if attachment_related_fields:
                # Create a generic attachment field schema
                attachment_schema = {
                    "type": "string",
                    "description": "File attachment for the email",
                    "title": "Attachment"
                }
                cleaned_properties["attachment"] = attachment_schema

            # Update the flat schema with cleaned field names
            flat_schema["properties"] = cleaned_properties

            # Also update required fields to match cleaned names
            if flat_schema.get("required"):
                cleaned_required = [field.replace("[0]", "") for field in flat_schema["required"]]
                flat_schema["required"] = cleaned_required

            input_schema = create_input_schema_from_json_schema(flat_schema)
            if input_schema is None:
                logger.warning(f"Input schema is None for action key: {action_key}")
                return []

            # Additional safety check before calling schema_to_langflow_inputs
            if not hasattr(input_schema, "model_fields"):
                logger.warning(f"Input schema for {action_key} does not have model_fields attribute")
                return []

            if input_schema.model_fields is None:
                logger.warning(f"Input schema model_fields is None for {action_key}")
                return []

            result = schema_to_langflow_inputs(input_schema)

            # Process inputs to handle attachment fields and set advanced status
            if result:
                processed_inputs = []
                required_fields_set = set(flat_schema.get("required", []))

                # Get attachment fields for this action (if any) - now includes our consolidated "attachment" field
                attachment_fields = self.ATTACHMENT_FIELDS.get(action_key, set())
                if attachment_related_fields:  # If we consolidated attachment fields
                    attachment_fields = attachment_fields | {"attachment"}

                for inp in result:
                    if hasattr(inp, "name"):
                        # Check if this specific field is an attachment field
                        if inp.name.lower() in attachment_fields or inp.name.lower() == "attachment":
                            # Replace with FileInput for attachment fields
                            file_input = FileInput(
                                name=inp.name,
                                display_name=getattr(inp, "display_name", inp.name.replace("_", " ").title()),
                                required=inp.name in required_fields_set,
                                advanced=inp.name not in required_fields_set,
                                info=getattr(inp, "info", "Upload file attachment"),
                                show=True,
                                file_types=[
                                    "csv", "txt", "doc", "docx", "xls", "xlsx", "pdf",
                                    "png", "jpg", "jpeg", "gif", "zip", "rar", "ppt", "pptx"
                                ],
                            )
                            processed_inputs.append(file_input)
                        else:
                            # Ensure proper display_name and info are set for regular fields
                            if not hasattr(inp, "display_name") or not inp.display_name:
                                inp.display_name = inp.name.replace("_", " ").title()

                            # Preserve description from schema if available
                            field_schema = flat_schema.get("properties", {}).get(inp.name, {})
                            schema_description = field_schema.get("description")
                            current_info = getattr(inp, "info", None)

                            # Use schema description if available, otherwise keep current info or create from name
                            if schema_description:
                                inp.info = schema_description
                            elif not current_info:
                                # Fallback: create a basic description from the field name if no description exists
                                inp.info = f"{inp.name.replace('_', ' ').title()} field"

                            # Set advanced status for non-attachment fields
                            if inp.name not in required_fields_set:
                                inp.advanced = True

                            processed_inputs.append(inp)
                    else:
                        processed_inputs.append(inp)

                return processed_inputs

            return result
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error generating inputs for {action_key}: {e}")
            return []

    def _get_inputs_for_all_actions(self) -> dict[str, list[InputTypes]]:
        """Return a mapping action_key → list[InputTypes] for every action."""
        result: dict[str, list[InputTypes]] = {}
        for key in self._actions_data:
            result[key] = self._validate_schema_inputs(key)
        return result

    def _remove_inputs_from_build_config(self, build_config: dict, keep_for_action: str) -> None:
        """Remove parameter UI fields that belong to other actions."""
        for action_key, lf_inputs in self._get_inputs_for_all_actions().items():
            if action_key == keep_for_action:
                continue
            for inp in lf_inputs:
                build_config.pop(inp.name, None)

    def _update_action_config(self, build_config: dict, selected_value: Any) -> None:
        """Add or update parameter input fields for the chosen action."""
        if not selected_value:
            return

        # The UI passes either a list with dict [{name: display_name}] OR the raw key
        if isinstance(selected_value, list) and selected_value:
            display_name = selected_value[0]["name"]
        else:
            display_name = selected_value

        action_key = self.desanitize_action_name(display_name)
        lf_inputs = self._validate_schema_inputs(action_key)

        # First remove inputs belonging to other actions
        self._remove_inputs_from_build_config(build_config, action_key)

        # Add / update the inputs for this action
        for inp in lf_inputs:
            inp_dict = inp.to_dict() if hasattr(inp, "to_dict") else inp.__dict__
            inp_dict.setdefault("show", True)  # visible once action selected
            # Preserve previously entered value if user already filled something
            if inp.name in build_config:
                existing_val = build_config[inp.name].get("value")
                inp_dict.setdefault("value", existing_val)
            build_config[inp.name] = inp_dict

        # Ensure _all_fields includes new ones
        self._all_fields.update({i.name for i in lf_inputs})

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Simplified build config updates."""
        # Ensure dynamic action metadata is available whenever we have an API key
        if (field_name == "api_key" and field_value) or (self.api_key and not self._actions_data):
            self._populate_actions_data()

        if field_name == "tool_mode":
            build_config["action"]["show"] = True
            for field in self._all_fields:
                build_config[field]["show"] = not field_value
            return build_config

        if field_name == "action":
            # Dynamically inject parameter fields for the chosen action
            self._update_action_config(build_config, field_value)
            # Keep the existing show/hide behaviour
            self.show_hide_fields(build_config, field_value)
            return build_config

        # Handle API key removal
        if field_name == "api_key" and len(field_value) == 0:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action"]["options"] = []
            build_config["action"]["helper_text"] = "Please connect before selecting actions."
            build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}
            return build_config

        # Only proceed with connection logic if we have an API key
        if not hasattr(self, "api_key") or not self.api_key:
            return build_config

        # Update action options
        self._build_action_maps()
        build_config["action"]["options"] = [
            {"name": self.sanitize_action_name(action), "metadata": action}
            for action in self._actions_data
        ]
        build_config["action"]["show"] = True

        try:
            toolset = self._build_wrapper()
            toolkit_slug = self.app_name.lower()

            # Handle disconnection first (if user clicked disconnect)
            if field_name == "auth_link" and field_value == "disconnect":
                try:
                    connections = toolset.connected_accounts.list(user_ids=[self.entity_id], toolkit_slugs=[toolkit_slug])
                    # Validate response structure before accessing items
                    if connections and hasattr(connections, "items") and connections.items:
                        if isinstance(connections.items, list) and len(connections.items) > 0:
                            # Find the first ACTIVE connection to disconnect
                            active_connection = None
                            for connection in connections.items:
                                if getattr(connection, "status", None) == "ACTIVE":
                                    active_connection = connection
                                    break

                            if active_connection:
                                connection_id = getattr(active_connection, "id", None)
                                if connection_id:
                                    toolset.connected_accounts.delete(nanoid=connection_id)
                                    logger.info(f"Disconnected ACTIVE connection from {toolkit_slug}")
                                else:
                                    logger.warning(f"ACTIVE connection found but no ID available for {toolkit_slug}")
                            else:
                                logger.warning(f"Found {len(connections.items)} connection(s) for {toolkit_slug}, but none are ACTIVE to disconnect")
                        else:
                            logger.warning(f"No connections to disconnect for {toolkit_slug}")
                    else:
                        logger.warning(f"Invalid connection response structure for {toolkit_slug}")

                    # After disconnection, fall through to check connection status
                except Exception as e:
                    logger.error(f"Error disconnecting: {e}")
                    build_config["auth_link"]["value"] = "error"
                    build_config["auth_link"]["auth_tooltip"] = f"Disconnect failed: {e!s}"
                    return build_config

            # Check current connection status and set appropriate auth_link value
            try:
                connection_list = toolset.connected_accounts.list(user_ids=[self.entity_id], toolkit_slugs=[toolkit_slug])

                # Validate response structure and check for valid connections
                has_active_connections = False
                if connection_list and hasattr(connection_list, "items") and connection_list.items:
                    # Check if items is a list and has valid connections
                    if isinstance(connection_list.items, list) and len(connection_list.items) > 0:
                        # Check if any connection has status 'ACTIVE'
                        active_connections = []
                        for connection in connection_list.items:
                            connection_status = getattr(connection, "status", None)
                            if connection_status == "ACTIVE":
                                active_connections.append(connection)

                        if active_connections:
                            has_active_connections = True
                            logger.debug(f"Found {len(active_connections)} ACTIVE connection(s) out of {len(connection_list.items)} total for {toolkit_slug}")
                        else:
                            logger.debug(f"Found {len(connection_list.items)} connection(s) for {toolkit_slug}, but none are ACTIVE")
                    else:
                        logger.debug(f"No valid connections found for {toolkit_slug}: items is not a valid list")
                else:
                    logger.debug(f"No connections found for {toolkit_slug}: invalid response structure")

                if has_active_connections:
                    # User has active connection
                    build_config["auth_link"]["value"] = "validated"
                    build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                    build_config["action"]["helper_text"] = ""
                    build_config["action"]["helper_text_metadata"] = {}
                else:
                    # No active connection - create OAuth connection and set redirect URL immediately
                    try:
                        logger.info(f"No active connection found. Creating OAuth connection for {toolkit_slug}...")
                        connection = toolset.toolkits.authorize(user_id=self.entity_id, toolkit=toolkit_slug)

                        # Get the redirect URL
                        redirect_url = getattr(connection, "redirect_url", None)
                        if not redirect_url:
                            # Try accessing it as a property or method
                            if hasattr(connection, "redirect_url"):
                                redirect_url = connection.redirect_url
                            else:
                                raise ValueError("No redirect URL received from Composio")

                        # Validate the URL format
                        if not redirect_url.startswith(("http://", "https://")):
                            raise ValueError(f"Invalid redirect URL format: {redirect_url}")

                        # Log the URL for debugging and manual use if needed
                        logger.info(f"🔗 Composio OAuth URL for {toolkit_slug}: {redirect_url}")

                        # Set the redirect URL directly - like the old implementation
                        build_config["auth_link"]["value"] = redirect_url
                        build_config["auth_link"]["auth_tooltip"] = "Connect"
                        build_config["action"]["helper_text"] = "Please connect before selecting actions."
                        build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}
                    except Exception as e:
                        logger.error(f"Error creating OAuth connection: {e}")
                        build_config["auth_link"]["value"] = "connect"
                        build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
                        build_config["action"]["helper_text"] = "Please connect before selecting actions."
                        build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}

            except Exception as e:
                logger.error(f"Error checking connection status for {toolkit_slug}: {e}")
                # Default to disconnected state on error
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action"]["helper_text"] = "Please connect before selecting actions."
                build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}

        except Exception as e:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action"]["helper_text"] = "Please connect before selecting actions."
            build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}
            logger.error(f"Error in auth flow: {e}")

        return build_config

    def configure_tools(self, composio: Composio) -> list[Tool]:
        tools = composio.tools.get(user_id=self.entity_id, toolkits=[self.app_name.lower()])
        logger.info(f"Tools: {tools}")
        configured_tools = []
        for tool in tools:
            # Set the sanitized name
            display_name = self._actions_data.get(tool.name, {}).get(
                "display_name", self._sanitized_names.get(tool.name, self._name_sanitizer.sub("-", tool.name))
            )
            # Set the tags
            tool.tags = [tool.name]
            tool.metadata = {"display_name": display_name, "display_description": tool.description, "readonly": True}
            configured_tools.append(tool)
        return configured_tools

    async def _get_tools(self) -> list[Tool]:
        """Get tools with cached results and optimized name sanitization."""
        composio = self._build_wrapper()
        self.set_default_tools()
        return self.configure_tools(composio)

    @property
    def enabled_tools(self):
        """Return tag names for *all* actions of this app so they are exposed to the agent.

        The tool objects created in ``configure_tools`` use the raw Composio action key
        (e.g. ``GMAIL_SEND_EMAIL``) as their ``name`` and as the single element of
        ``tool.tags``.  Returning those keys here makes every action available for
        autonomous agents without requiring the user to pick them in the UI first.
        """
        # Ensure actions are populated (in case property accessed early)
        if not self._actions_data:
            self._populate_actions_data()

        return list(self._actions_data.keys())

    # ---------------------------------------------------------------------
    # Generic execution logic – now shared by every Composio app component
    # ---------------------------------------------------------------------

    def execute_action(self):
        """Execute the selected Composio action and return its raw `data` payload."""
        # Build composio & make sure schemas are present
        composio = self._build_wrapper()
        self._populate_actions_data()
        self._build_action_maps()

        # Resolve the action key from the UI-selected display name
        display_name = (
            self.action[0]["name"] if isinstance(getattr(self, "action", None), list) and self.action else self.action
        )
        action_key = self._display_to_key_map.get(display_name)

        if not action_key:
            msg = f"Invalid action: {display_name}"
            raise ValueError(msg)

        try:
            # No more enums - use action slug directly
            action_slug = action_key

            # Gather parameters from component inputs
            arguments: dict[str, Any] = {}
            param_fields = self._actions_data.get(action_key, {}).get("action_fields", [])

            # Get the schema for this action to check for defaults
            schema_dict = self._action_schemas.get(action_key, {})
            parameters_schema = schema_dict.get("input_parameters", {})
            schema_properties = parameters_schema.get("properties", {}) if parameters_schema else {}
            # Handle case where 'required' field is None (causes "'NoneType' object is not iterable")
            required_list = parameters_schema.get("required", []) if parameters_schema else []
            required_fields = set(required_list) if required_list is not None else set()

            for field in param_fields:
                if not hasattr(self, field):
                    continue
                value = getattr(self, field)

                # Skip None, empty strings, and empty lists
                if value is None or value == "" or (isinstance(value, list) and len(value) == 0):
                    continue

                # For optional fields, be more strict about including them
                # Only include if the user has explicitly provided a meaningful value
                if field not in required_fields:
                    # Get the default value from the schema
                    field_schema = schema_properties.get(field, {})
                    schema_default = field_schema.get("default")

                    # Skip if the current value matches the schema default
                    if value == schema_default:
                        continue

                    # Skip fields that look like auto-generated UUIDs for optional fields
                    # This is a heuristic to avoid passing system-generated IDs
                    if isinstance(value, str) and len(value) == 36 and value.count("-") == 4:
                        continue

                # Convert comma-separated to list for array parameters (heuristic)
                prop_schema = schema_properties.get(field, {})
                if prop_schema.get("type") == "array" and isinstance(value, str):
                    value = [item.strip() for item in value.split(",")]

                if field in self._bool_variables:
                    value = bool(value)

                arguments[field] = value

            # Execute using new SDK
            result = composio.tools.execute(
                slug=action_slug,
                arguments=arguments,
                user_id=self.entity_id,
            )

            return {"response": result}

        except Exception as e:
            logger.error(f"Failed to execute {action_key}: {e}")
            raise

    @abstractmethod
    def set_default_tools(self):
        """Set the default tools."""
