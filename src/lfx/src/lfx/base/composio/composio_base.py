import copy
import json
import re
from contextlib import suppress
from typing import Any

from composio import Composio
from composio_langchain import LangchainProvider
from langchain_core.tools import Tool

from lfx.base.mcp.util import create_input_schema_from_json_schema
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import (
    AuthInput,
    DropdownInput,
    FileInput,
    InputTypes,
    MessageTextInput,
    MultilineInput,
    SecretStrInput,
    SortableListInput,
    StrInput,
    TabInput,
)
from lfx.io import Output
from lfx.io.schema import flatten_schema, schema_to_langflow_inputs
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


class ComposioBaseComponent(Component):
    """Base class for Composio components with common functionality."""

    default_tools_limit: int = 5

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
        DropdownInput(
            name="auth_mode",
            display_name="Auth Mode",
            options=[],
            placeholder="Select auth mode",
            toggle=True,
            toggle_disable=True,
            show=False,
            real_time_refresh=True,
            helper_text="Choose how to authenticate with the toolkit.",
        ),
        AuthInput(
            name="auth_link",
            value="",
            auth_tooltip="Please insert a valid Composio API Key.",
            show=False,
        ),
        # Pre-defined placeholder fields for dynamic auth - hidden by default
        SecretStrInput(
            name="client_id",
            display_name="Client ID",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="client_secret",
            display_name="Client Secret",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="verification_token",
            display_name="Verification Token",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="redirect_uri",
            display_name="Redirect URI",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="authorization_url",
            display_name="Authorization URL",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="token_url",
            display_name="Token URL",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        # API Key auth fields
        SecretStrInput(
            name="api_key_field",
            display_name="API Key",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="generic_api_key",
            display_name="API Key",
            info="Enter API key on Composio page",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Token",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="access_token",
            display_name="Access Token",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="refresh_token",
            display_name="Refresh Token",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        # Basic Auth fields
        StrInput(
            name="username",
            display_name="Username",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="password",
            display_name="Password",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        # Other common auth fields
        StrInput(
            name="domain",
            display_name="Domain",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="bearer_token",
            display_name="Bearer Token",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="authorization_code",
            display_name="Authorization Code",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="scopes",
            display_name="Scopes",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        # Add more common auth fields
        StrInput(
            name="subdomain",
            display_name="Subdomain",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="instance_url",
            display_name="Instance URL",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="tenant_id",
            display_name="Tenant ID",
            info="",
            show=False,
            value="",
            required=False,
            real_time_refresh=True,
        ),
        SortableListInput(
            name="action_button",
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

    _name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")

    # Class-level caches
    _actions_cache: dict[str, dict[str, Any]] = {}
    _action_schema_cache: dict[str, dict[str, Any]] = {}
    # Track all auth field names discovered across all toolkits
    _all_auth_field_names: set[str] = set()

    @classmethod
    def get_actions_cache(cls) -> dict[str, dict[str, Any]]:
        """Get the class-level actions cache."""
        return cls._actions_cache

    @classmethod
    def get_action_schema_cache(cls) -> dict[str, dict[str, Any]]:
        """Get the class-level action schema cache."""
        return cls._action_schema_cache

    @classmethod
    def get_all_auth_field_names(cls) -> set[str]:
        """Get all auth field names discovered across toolkits."""
        return cls._all_auth_field_names

    outputs = [
        Output(name="dataFrame", display_name="DataFrame", method="as_dataframe"),
    ]

    inputs = list(_base_inputs)

    def __init__(self, **kwargs):
        """Initialize instance variables to prevent shared state between components."""
        super().__init__(**kwargs)
        self._all_fields: set[str] = set()
        self._bool_variables: set[str] = set()
        self._actions_data: dict[str, dict[str, Any]] = {}
        self._default_tools: set[str] = set()
        self._display_to_key_map: dict[str, str] = {}
        self._key_to_display_map: dict[str, str] = {}
        self._sanitized_names: dict[str, str] = {}
        self._action_schemas: dict[str, Any] = {}
        # Toolkit schema cache per instance
        self._toolkit_schema: dict[str, Any] | None = None
        # Track generated custom auth inputs to hide/show/reset
        self._auth_dynamic_fields: set[str] = set()

    def as_message(self) -> Message:
        result = self.execute_action()
        if result is None:
            return Message(text="Action execution returned no result")
        return Message(text=str(result))

    def as_dataframe(self) -> DataFrame:
        result = self.execute_action()

        if isinstance(result, dict):
            result = [result]
        # Build DataFrame and avoid exposing a 'data' attribute via column access,
        # which interferes with logging utilities that probe for '.data'.
        df = DataFrame(result)
        if "data" in df.columns:
            df = df.rename(columns={"data": "_data"})
        return df

    def as_data(self) -> Data:
        result = self.execute_action()
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
        return self._key_to_display_map.get(action_name, action_name)

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
        """Fetch the list of actions for the toolkit and build helper maps."""
        if self._actions_data:
            return

        # Try to load from the class-level cache
        toolkit_slug = self.app_name.lower()
        if toolkit_slug in self.__class__.get_actions_cache():
            # Deep-copy so that any mutation on this instance does not affect the
            # cached master copy.
            self._actions_data = copy.deepcopy(self.__class__.get_actions_cache()[toolkit_slug])
            self._action_schemas = copy.deepcopy(self.__class__.get_action_schema_cache().get(toolkit_slug, {}))
            logger.debug(f"Loaded actions for {toolkit_slug} from in-process cache")
            return

        api_key = getattr(self, "api_key", None)
        if not api_key:
            logger.warning("API key is missing. Cannot populate actions data.")
            return

        try:
            composio = self._build_wrapper()
            toolkit_slug = self.app_name.lower()

            raw_tools = composio.tools.get_raw_composio_tools(toolkits=[toolkit_slug], limit=999)

            if not raw_tools:
                msg = f"Toolkit '{toolkit_slug}' not found or has no available tools"
                raise ValueError(msg)

            for raw_tool in raw_tools:
                try:
                    # Convert raw_tool to dict-like structure
                    tool_dict = raw_tool.__dict__ if hasattr(raw_tool, "__dict__") else raw_tool

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
                        # Extract version information from the tool
                        version = tool_dict.get("version")
                        available_versions = tool_dict.get("available_versions", [])

                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                            "file_upload_fields": set(),
                            "version": version,
                            "available_versions": available_versions,
                        }
                        continue

                    try:
                        # Special handling for unusual schema structures
                        if not isinstance(parameters_schema, dict):
                            # Try to convert if it's a model object
                            if hasattr(parameters_schema, "model_dump"):
                                parameters_schema = parameters_schema.model_dump()
                            elif hasattr(parameters_schema, "__dict__"):
                                parameters_schema = parameters_schema.__dict__
                            else:
                                logger.warning(f"Cannot process parameters schema for {action_key}, skipping")
                                # Extract version information from the tool
                                version = tool_dict.get("version")
                                available_versions = tool_dict.get("available_versions", [])

                                self._action_schemas[action_key] = tool_dict
                                self._actions_data[action_key] = {
                                    "display_name": display_name,
                                    "action_fields": [],
                                    "file_upload_fields": set(),
                                    "version": version,
                                    "available_versions": available_versions,
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
                        except (KeyError, TypeError, ValueError):
                            # Extract version information from the tool
                            version = tool_dict.get("version")
                            available_versions = tool_dict.get("available_versions", [])

                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                                "file_upload_fields": set(),
                                "version": version,
                                "available_versions": available_versions,
                            }
                            continue

                        if flat_schema is None:
                            logger.warning(f"Flat schema is None for action key: {action_key}")
                            # Still add the action but with empty fields so the UI doesn't break
                            # Extract version information from the tool
                            version = tool_dict.get("version")
                            available_versions = tool_dict.get("available_versions", [])

                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                                "file_upload_fields": set(),
                                "version": version,
                                "available_versions": available_versions,
                            }
                            continue

                        # Extract field names and detect file upload fields during parsing
                        raw_action_fields = list(flat_schema.get("properties", {}).keys())
                        action_fields = []
                        attachment_related_found = False
                        file_upload_fields = set()

                        # Check original schema properties for file_uploadable fields
                        original_props = parameters_schema.get("properties", {})

                        # Determine top-level fields that should be treated as single JSON inputs
                        json_parent_fields = set()
                        for top_name, top_schema in original_props.items():
                            if isinstance(top_schema, dict) and top_schema.get("type") in {"object", "array"}:
                                json_parent_fields.add(top_name)

                        for field_name, field_schema in original_props.items():
                            if isinstance(field_schema, dict):
                                clean_field_name = field_name.replace("[0]", "")
                                # Check direct file_uploadable attribute
                                if field_schema.get("file_uploadable") is True:
                                    file_upload_fields.add(clean_field_name)

                                # Check anyOf structures (like OUTLOOK_OUTLOOK_SEND_EMAIL)
                                if "anyOf" in field_schema:
                                    for any_of_item in field_schema["anyOf"]:
                                        if isinstance(any_of_item, dict) and any_of_item.get("file_uploadable") is True:
                                            file_upload_fields.add(clean_field_name)

                        for field in raw_action_fields:
                            clean_field = field.replace("[0]", "")
                            # Skip subfields of JSON parents; we will expose the parent as a single field
                            top_prefix = clean_field.split(".")[0].split("[")[0]
                            if top_prefix in json_parent_fields and "." in clean_field:
                                continue
                            # Check if this field is attachment-related
                            if clean_field.lower().startswith("attachment."):
                                attachment_related_found = True
                                continue  # Skip individual attachment fields

                            # Handle conflicting field names - rename user_id to avoid conflicts with entity_id
                            if clean_field == "user_id":
                                clean_field = f"{self.app_name}_user_id"

                            # Handle reserved attribute name conflicts (e.g., 'status', 'name')
                            # Prefix with app name to prevent clashes with component attributes
                            if clean_field in {"status", "name"}:
                                clean_field = f"{self.app_name}_{clean_field}"

                            action_fields.append(clean_field)

                        # Add consolidated attachment field if we found attachment-related fields
                        if attachment_related_found:
                            action_fields.append("attachment")
                            file_upload_fields.add("attachment")  # Attachment fields are also file upload fields

                        # Ensure parents for object/array are present as fields (single JSON field)
                        for parent in json_parent_fields:
                            if parent not in action_fields:
                                action_fields.append(parent)

                        # Track boolean parameters so we can coerce them later
                        properties = flat_schema.get("properties", {})
                        if properties:
                            for p_name, p_schema in properties.items():
                                if isinstance(p_schema, dict) and p_schema.get("type") == "boolean":
                                    # Use cleaned field name for boolean tracking
                                    clean_field_name = p_name.replace("[0]", "")
                                    self._bool_variables.add(clean_field_name)

                        # Extract version information from the tool
                        version = tool_dict.get("version")
                        available_versions = tool_dict.get("available_versions", [])

                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": action_fields,
                            "file_upload_fields": file_upload_fields,
                            "version": version,
                            "available_versions": available_versions,
                        }

                    except (KeyError, TypeError, ValueError) as flatten_error:
                        logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                        # Extract version information from the tool
                        version = tool_dict.get("version")
                        available_versions = tool_dict.get("available_versions", [])

                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                            "file_upload_fields": set(),
                            "version": version,
                            "available_versions": available_versions,
                        }
                        continue

                except ValueError as e:
                    logger.warning(f"Failed processing Composio tool for action {raw_tool}: {e}")

            # Helper look-ups used elsewhere
            self._all_fields = {f for d in self._actions_data.values() for f in d["action_fields"]}
            self._build_action_maps()

            # Cache actions for this toolkit so subsequent component instances
            # can reuse them without hitting the Composio API again.
            self.__class__.get_actions_cache()[toolkit_slug] = copy.deepcopy(self._actions_data)
            self.__class__.get_action_schema_cache()[toolkit_slug] = copy.deepcopy(self._action_schemas)

        except ValueError as e:
            logger.debug(f"Could not populate Composio actions for {self.app_name}: {e}")

    def _validate_schema_inputs(self, action_key: str) -> list[InputTypes]:
        """Convert the JSON schema for *action_key* into Langflow input objects."""
        # Skip validation for default/placeholder values
        if action_key in ("disabled", "placeholder", ""):
            logger.debug(f"Skipping schema validation for placeholder value: {action_key}")
            return []

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
                logger.warning(
                    f"Parameters schema is not a dict for action key: {action_key}, got: {type(parameters_schema)}"
                )
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

            # Also get top-level required fields from original schema
            original_required = set(parameters_schema.get("required", []))

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
            except (KeyError, TypeError, ValueError) as flatten_error:
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

                # Handle conflicting field names - rename user_id to avoid conflicts with entity_id
                if clean_field_name == "user_id":
                    clean_field_name = f"{self.app_name}_user_id"
                    # Update the field schema description to reflect the name change
                    field_schema_copy = field_schema.copy()
                    field_schema_copy["description"] = (
                        f"User ID for {self.app_name.title()}: " + field_schema["description"]
                    )
                elif clean_field_name == "status":
                    clean_field_name = f"{self.app_name}_status"
                    # Update the field schema description to reflect the name change
                    field_schema_copy = field_schema.copy()
                    field_schema_copy["description"] = f"Status for {self.app_name.title()}: " + field_schema.get(
                        "description", ""
                    )
                elif clean_field_name == "name":
                    clean_field_name = f"{self.app_name}_name"
                    # Update the field schema description to reflect the name change
                    field_schema_copy = field_schema.copy()
                    field_schema_copy["description"] = f"Name for {self.app_name.title()}: " + field_schema.get(
                        "description", ""
                    )
                else:
                    # Use the original field schema for all other fields
                    field_schema_copy = field_schema

                # Preserve the full schema information, not just the type
                cleaned_properties[clean_field_name] = field_schema_copy

            # If we found attachment-related fields, add a single "attachment" field
            if attachment_related_fields:
                # Create a generic attachment field schema
                attachment_schema = {
                    "type": "string",
                    "description": "File attachment for the email",
                    "title": "Attachment",
                }
                cleaned_properties["attachment"] = attachment_schema

            # Update the flat schema with cleaned field names
            flat_schema["properties"] = cleaned_properties

            # Also update required fields to match cleaned names
            if flat_schema.get("required"):
                cleaned_required = []
                for field in flat_schema["required"]:
                    base = field.replace("[0]", "")
                    if base == "user_id":
                        cleaned_required.append(f"{self.app_name}_user_id")
                    elif base == "status":
                        cleaned_required.append(f"{self.app_name}_status")
                    elif base == "name":
                        cleaned_required.append(f"{self.app_name}_name")
                    else:
                        cleaned_required.append(base)
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

                # Get file upload fields from stored action data
                file_upload_fields = self._actions_data.get(action_key, {}).get("file_upload_fields", set())
                if attachment_related_fields:  # If we consolidated attachment fields
                    file_upload_fields = file_upload_fields | {"attachment"}

                # Identify top-level JSON parents (object/array) to render as single CodeInput
                top_props_for_json = set()
                props_dict = parameters_schema.get("properties", {}) if isinstance(parameters_schema, dict) else {}
                for top_name, top_schema in props_dict.items():
                    if isinstance(top_schema, dict) and top_schema.get("type") in {"object", "array"}:
                        top_props_for_json.add(top_name)

                for inp in result:
                    if hasattr(inp, "name") and inp.name is not None:
                        # Skip flattened subfields of JSON parents; handle array prefixes (e.g., parent[0].x)
                        raw_prefix = inp.name.split(".")[0]
                        base_prefix = raw_prefix.replace("[0]", "")
                        if base_prefix in top_props_for_json and ("." in inp.name or "[" in inp.name):
                            continue
                        # Check if this specific field is a file upload field
                        if inp.name.lower() in file_upload_fields or inp.name.lower() == "attachment":
                            # Replace with FileInput for file upload fields
                            file_input = FileInput(
                                name=inp.name,
                                display_name=getattr(inp, "display_name", inp.name.replace("_", " ").title()),
                                required=inp.name in required_fields_set,
                                advanced=inp.name not in required_fields_set,
                                info=getattr(inp, "info", "Upload file for this field"),
                                show=True,
                                file_types=[
                                    "csv",
                                    "txt",
                                    "doc",
                                    "docx",
                                    "xls",
                                    "xlsx",
                                    "pdf",
                                    "png",
                                    "jpg",
                                    "jpeg",
                                    "gif",
                                    "zip",
                                    "rar",
                                    "ppt",
                                    "pptx",
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

                            # Set advanced status for non-file-upload fields
                            if inp.name not in required_fields_set:
                                inp.advanced = True

                            # Skip entity_id being mapped to user_id parameter
                            if inp.name == "user_id" and getattr(self, "entity_id", None) == getattr(
                                inp, "value", None
                            ):
                                continue

                            processed_inputs.append(inp)
                    else:
                        processed_inputs.append(inp)

                # Add single CodeInput for each JSON parent field
                props_dict = parameters_schema.get("properties", {}) if isinstance(parameters_schema, dict) else {}
                for top_name in top_props_for_json:
                    # Avoid duplicates if already present
                    if any(getattr(i, "name", None) == top_name for i in processed_inputs):
                        continue
                    top_schema = props_dict.get(top_name, {})
                    # For MultilineInput fields (complex JSON objects/arrays)
                    is_required = top_name in original_required
                    processed_inputs.append(
                        MultilineInput(
                            name=top_name,
                            display_name=top_schema.get("title") or top_name.replace("_", " ").title(),
                            info=(
                                top_schema.get("description") or "Provide JSON for this parameter (object or array)."
                            ),
                            required=is_required,  # Setting original schema
                        )
                    )

                return processed_inputs
            return result  # noqa: TRY300
        except ValueError as e:
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
        protected_keys = {"code", "entity_id", "api_key", "auth_link", "action_button", "tool_mode"}

        for action_key, lf_inputs in self._get_inputs_for_all_actions().items():
            if action_key == keep_for_action:
                continue
            for inp in lf_inputs:
                if inp.name is not None and inp.name not in protected_keys:
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

        # Skip validation for default/placeholder values
        if action_key in ("disabled", "placeholder", ""):
            logger.debug(f"Skipping action config update for placeholder value: {action_key}")
            return

        lf_inputs = self._validate_schema_inputs(action_key)

        # First remove inputs belonging to other actions
        self._remove_inputs_from_build_config(build_config, action_key)

        # Add / update the inputs for this action
        for inp in lf_inputs:
            if inp.name is not None:
                inp_dict = inp.to_dict() if hasattr(inp, "to_dict") else inp.__dict__.copy()

                # Do not mutate input_types here; keep original configuration

                inp_dict.setdefault("show", True)  # visible once action selected
                # Preserve previously entered value if user already filled something
                if inp.name in build_config:
                    existing_val = build_config[inp.name].get("value")
                    inp_dict.setdefault("value", existing_val)
                build_config[inp.name] = inp_dict

        # Ensure _all_fields includes new ones
        self._all_fields.update({i.name for i in lf_inputs if i.name is not None})

        # Normalize input_types to prevent None values
        self.update_input_types(build_config)

    def _is_tool_mode_enabled(self) -> bool:
        """Check if tool_mode is currently enabled."""
        return getattr(self, "tool_mode", False)

    def _set_action_visibility(self, build_config: dict, *, force_show: bool | None = None) -> None:
        """Set action field visibility based on tool_mode state or forced value."""
        if force_show is not None:
            build_config["action_button"]["show"] = force_show
        else:
            # When tool_mode is enabled, hide action field
            build_config["action_button"]["show"] = not self._is_tool_mode_enabled()

    def create_new_auth_config(self, app_name: str) -> str:
        """Create a new auth config for the given app name."""
        composio = self._build_wrapper()
        auth_config = composio.auth_configs.create(toolkit=app_name, options={"type": "use_composio_managed_auth"})
        return auth_config.id

    def _initiate_connection(self, app_name: str) -> tuple[str, str]:
        """Initiate connection using link method and return (redirect_url, connection_id)."""
        try:
            composio = self._build_wrapper()

            # Always create a new auth config (previous behavior)
            auth_config_id = self.create_new_auth_config(app_name)

            connection_request = composio.connected_accounts.link(user_id=self.entity_id, auth_config_id=auth_config_id)

            redirect_url = getattr(connection_request, "redirect_url", None)
            connection_id = getattr(connection_request, "id", None)

            if not redirect_url or not redirect_url.startswith(("http://", "https://")):
                msg = "Invalid redirect URL received from Composio"
                raise ValueError(msg)

            if not connection_id:
                msg = "No connection ID received from Composio"
                raise ValueError(msg)

            logger.info(f"Connection initiated for {app_name}: {redirect_url} (ID: {connection_id})")
            return redirect_url, connection_id  # noqa: TRY300

        except (ValueError, ConnectionError, TypeError, AttributeError) as e:
            logger.error(f"Error initiating connection for {app_name}: {e}")
            msg = f"Failed to initiate connection: {e}"
            raise ValueError(msg) from e

    def _check_connection_status_by_id(self, connection_id: str) -> str | None:
        """Check status of a specific connection by ID. Returns status or None if not found."""
        try:
            composio = self._build_wrapper()
            connection = composio.connected_accounts.get(nanoid=connection_id)
            status = getattr(connection, "status", None)
            logger.info(f"Connection {connection_id} status: {status}")
        except (ValueError, ConnectionError) as e:
            logger.error(f"Error checking connection {connection_id}: {e}")
            return None
        else:
            return status

    def _find_active_connection_for_app(self, app_name: str) -> tuple[str, str] | None:
        """Find any ACTIVE connection for this app/user. Returns (connection_id, status) or None."""
        try:
            composio = self._build_wrapper()
            connection_list = composio.connected_accounts.list(
                user_ids=[self.entity_id], toolkit_slugs=[app_name.lower()]
            )

            if connection_list and hasattr(connection_list, "items") and connection_list.items:
                for connection in connection_list.items:
                    connection_id = getattr(connection, "id", None)
                    connection_status = getattr(connection, "status", None)
                    if connection_status == "ACTIVE" and connection_id:
                        logger.info(f"Found existing ACTIVE connection for {app_name}: {connection_id}")
                        return connection_id, connection_status

        except (ValueError, ConnectionError) as e:
            logger.error(f"Error finding active connection for {app_name}: {e}")
            return None
        else:
            return None

    def _get_connection_auth_info(self, connection_id: str) -> tuple[str | None, bool | None]:
        """Return (auth_scheme, is_composio_managed) for a given connection id, if available."""
        try:
            composio = self._build_wrapper()
            connection = composio.connected_accounts.get(nanoid=connection_id)
            auth_config = getattr(connection, "auth_config", None)
            if auth_config is None and hasattr(connection, "__dict__"):
                auth_config = getattr(connection.__dict__, "auth_config", None)
            scheme = getattr(auth_config, "auth_scheme", None) if auth_config else None
            is_managed = getattr(auth_config, "is_composio_managed", None) if auth_config else None
        except (AttributeError, ValueError, ConnectionError, TypeError) as e:
            logger.debug(f"Could not retrieve auth info for connection {connection_id}: {e}")
            return None, None
        else:
            return scheme, is_managed

    def _disconnect_specific_connection(self, connection_id: str) -> None:
        """Disconnect a specific Composio connection by ID."""
        try:
            composio = self._build_wrapper()
            composio.connected_accounts.delete(nanoid=connection_id)
            logger.info(f"✅ Disconnected specific connection: {connection_id}")

        except Exception as e:
            logger.error(f"Error disconnecting connection {connection_id}: {e}")
            msg = f"Failed to disconnect connection {connection_id}: {e}"
            raise ValueError(msg) from e

    def _to_plain_dict(self, obj: Any) -> Any:
        """Recursively convert SDK models/lists to plain Python dicts/lists for safe .get access."""
        try:
            if isinstance(obj, dict):
                return {k: self._to_plain_dict(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set)):
                return [self._to_plain_dict(v) for v in obj]
            if hasattr(obj, "model_dump"):
                try:
                    return self._to_plain_dict(obj.model_dump())
                except (TypeError, AttributeError, ValueError):
                    pass
            if hasattr(obj, "__dict__") and not isinstance(obj, (str, bytes)):
                try:
                    return self._to_plain_dict({k: v for k, v in obj.__dict__.items() if not k.startswith("_")})
                except (TypeError, AttributeError, ValueError):
                    pass
        except (TypeError, ValueError, AttributeError, RecursionError):
            return obj
        else:
            return obj

    def _get_toolkit_schema(self) -> dict[str, Any] | None:
        """Fetch and cache toolkit schema for auth details (modes and fields)."""
        if self._toolkit_schema is not None:
            return self._toolkit_schema
        try:
            composio = self._build_wrapper()
            app_slug = getattr(self, "app_name", "").lower()
            if not app_slug:
                return None
            # Use the correct Composio SDK method
            schema = composio.toolkits.get(slug=app_slug)
            self._toolkit_schema = self._to_plain_dict(schema)
        except (AttributeError, ValueError, ConnectionError, TypeError) as e:
            logger.debug(f"Could not retrieve toolkit schema for {getattr(self, 'app_name', '')}: {e}")
            return None
        else:
            return self._toolkit_schema

    def _extract_auth_modes_from_schema(self, schema: dict[str, Any] | None) -> list[str]:
        """Return available auth modes (e.g., OAUTH2, API_KEY) from toolkit schema."""
        if not schema:
            return []
        modes: list[str] = []
        # composio_managed_auth_schemes: list[str]
        managed = schema.get("composio_managed_auth_schemes") or schema.get("composioManagedAuthSchemes") or []
        has_managed_schemes = isinstance(managed, list) and len(managed) > 0

        # Add "Composio_Managed" as first option if there are managed schemes
        if has_managed_schemes:
            modes.append("Composio_Managed")

        # auth_config_details: list with entries containing mode
        details = schema.get("auth_config_details") or schema.get("authConfigDetails") or []
        for item in details:
            mode = item.get("mode") or item.get("auth_method")
            if isinstance(mode, str) and mode not in modes:
                modes.append(mode)
        return modes

    def _render_auth_mode_dropdown(self, build_config: dict, modes: list[str]) -> None:
        """Populate and show the auth_mode control; if only one mode, show as selected chip-style list."""
        try:
            build_config.setdefault("auth_mode", {})
            auth_mode_cfg = build_config["auth_mode"]
            # Prefer the connected scheme if known; otherwise use schema-provided modes as-is
            stored_scheme = (build_config.get("auth_link") or {}).get("auth_scheme")
            if isinstance(stored_scheme, str) and stored_scheme:
                modes = [stored_scheme]

            if len(modes) <= 1:
                # Single mode → show a pill in the auth_mode slot (right after API Key)
                selected = modes[0] if modes else ""
                try:
                    pill = TabInput(
                        name="auth_mode",
                        display_name="Auth Mode",
                        options=[selected] if selected else [],
                        value=selected,
                    ).to_dict()
                    pill["show"] = True
                    build_config["auth_mode"] = pill
                except (TypeError, ValueError, AttributeError):
                    build_config["auth_mode"] = {
                        "name": "auth_mode",
                        "display_name": "Auth Mode",
                        "type": "tab",
                        "options": [selected],
                        "value": selected,
                        "show": True,
                    }
            else:
                # Multiple modes → normal dropdown, hide the display chip if present
                auth_mode_cfg["options"] = modes
                auth_mode_cfg["show"] = True
                if not auth_mode_cfg.get("value") and modes:
                    auth_mode_cfg["value"] = modes[0]
                if "auth_mode_display" in build_config:
                    build_config["auth_mode_display"]["show"] = False
            auth_mode_cfg["helper_text"] = "Choose how to authenticate with the toolkit."
        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"Failed to render auth_mode dropdown: {e}")

    def _insert_field_before_action_button(self, build_config: dict, field_name: str, field_data: dict) -> None:
        """Insert a field in the correct position (before action_button) in build_config."""
        # If field already exists, don't add it again
        if field_name in build_config:
            return

        # If action_button doesn't exist, just add the field normally
        if "action_button" not in build_config:
            build_config[field_name] = field_data
            return

        # Find all the keys we need to preserve order for
        keys_before_action = []
        keys_after_action = []
        found_action = False

        for key in list(build_config.keys()):
            if key == "action_button":
                found_action = True
                keys_after_action.append(key)
            elif found_action:
                keys_after_action.append(key)
            else:
                keys_before_action.append(key)

        # Create new ordered dict
        new_config = {}

        # Add all fields before action_button
        for key in keys_before_action:
            new_config[key] = build_config[key]

        # Add the new field
        new_config[field_name] = field_data

        # Add action_button and all fields after it
        for key in keys_after_action:
            new_config[key] = build_config[key]

        # Clear and update build_config to maintain reference
        build_config.clear()
        build_config.update(new_config)

    def _clear_auth_dynamic_fields(self, build_config: dict) -> None:
        for fname in list(self._auth_dynamic_fields):
            if fname in build_config and isinstance(build_config[fname], dict):
                # Hide and reset instead of removing
                build_config[fname]["show"] = False
                build_config[fname]["value"] = ""
                build_config[fname]["required"] = False
        self._auth_dynamic_fields.clear()

    def _add_text_field(
        self,
        build_config: dict,
        name: str,
        display_name: str,
        info: str | None,
        *,
        required: bool,
        default_value: str | None = None,
    ) -> None:
        """Update existing field or add new text input for custom auth forms."""
        # Check if field already exists in build_config (pre-defined placeholder)
        if name in build_config:
            # Update existing field properties
            build_config[name]["display_name"] = display_name or name.replace("_", " ").title()
            build_config[name]["info"] = info or ""
            build_config[name]["required"] = required
            build_config[name]["show"] = True
            if default_value is not None and default_value != "":
                build_config[name]["value"] = default_value
        else:
            # Create new field if it doesn't exist
            # Use SecretStrInput for sensitive fields
            sensitive_fields = {
                "client_id",
                "client_secret",
                "api_key",
                "api_key_field",
                "generic_api_key",
                "token",
                "access_token",
                "refresh_token",
                "password",
                "bearer_token",
                "authorization_code",
            }

            if name in sensitive_fields:
                field = SecretStrInput(
                    name=name,
                    display_name=display_name or name.replace("_", " ").title(),
                    info=info or "",
                    required=required,
                    real_time_refresh=True,
                    show=True,
                ).to_dict()
            else:
                field = StrInput(
                    name=name,
                    display_name=display_name or name.replace("_", " ").title(),
                    info=info or "",
                    required=required,
                    real_time_refresh=True,
                    show=True,
                ).to_dict()

            if default_value is not None and default_value != "":
                field["value"] = default_value

            # Insert the field in the correct position (before action_button)
            self._insert_field_before_action_button(build_config, name, field)

        self._auth_dynamic_fields.add(name)
        # Also add to class-level cache for better tracking
        self.__class__.get_all_auth_field_names().add(name)

    def _render_custom_auth_fields(self, build_config: dict, schema: dict[str, Any], mode: str) -> None:
        """Render fields for custom auth based on schema auth_config_details sections."""
        details = schema.get("auth_config_details") or schema.get("authConfigDetails") or []
        selected = None
        for item in details:
            if (item.get("mode") or item.get("auth_method")) == mode:
                selected = item
                break
        if not selected:
            return
        fields = selected.get("fields") or {}

        # Helper function to process fields
        def process_fields(field_list: list, *, required: bool) -> None:
            for field in field_list:
                name = field.get("name")
                if not name:
                    continue
                # Skip Access Token field (bearer_token)
                if name == "bearer_token":
                    continue
                # Skip fields with default values for both required and optional fields
                default_val = field.get("default")
                if default_val is not None:
                    continue
                disp = field.get("display_name") or field.get("displayName") or name
                desc = field.get("description")
                self._add_text_field(build_config, name, disp, desc, required=required, default_value=default_val)

        # Only process AuthConfigCreation fields (for custom OAuth2, etc.)
        # Connection initiation fields are now handled on Composio page via link method
        creation = fields.get("auth_config_creation") or fields.get("authConfigCreation") or {}
        # Process required fields
        process_fields(creation.get("required", []), required=True)
        # Process optional fields (excluding those with defaults and bearer_token)
        process_fields(creation.get("optional", []), required=False)

    def _collect_all_auth_field_names(self, schema: dict[str, Any] | None) -> set[str]:
        names: set[str] = set()
        if not schema:
            return names
        details = schema.get("auth_config_details") or schema.get("authConfigDetails") or []
        for item in details:
            fields = (item.get("fields") or {}) if isinstance(item, dict) else {}
            for section_key in (
                "auth_config_creation",
                "authConfigCreation",
                "connected_account_initiation",
                "connectedAccountInitiation",
            ):
                section = fields.get(section_key) or {}
                for bucket in ("required", "optional"):
                    for entry in section.get(bucket, []) or []:
                        name = entry.get("name") if isinstance(entry, dict) else None
                        if name:
                            names.add(name)
                            # Add to class-level cache for tracking all discovered auth fields
                            self.__class__.get_all_auth_field_names().add(name)
        # Only use names discovered from the toolkit schema; do not add aliases
        return names

    def _clear_auth_fields_from_schema(self, build_config: dict, schema: dict[str, Any] | None) -> None:
        all_names = self._collect_all_auth_field_names(schema)
        for name in list(all_names):
            if name in build_config and isinstance(build_config[name], dict):
                # Hide and reset instead of removing to ensure UI updates immediately
                build_config[name]["show"] = False
                build_config[name]["value"] = ""
        # Also clear any tracked dynamic fields
        self._clear_auth_dynamic_fields(build_config)

    def update_input_types(self, build_config: dict) -> dict:
        """Normalize input_types to [] wherever None appears in the build_config template."""
        try:
            for key, value in list(build_config.items()):
                if isinstance(value, dict):
                    if value.get("input_types") is None:
                        build_config[key]["input_types"] = []
                elif hasattr(value, "input_types") and value.input_types is None:
                    with suppress(AttributeError, TypeError):
                        value.input_types = []
        except (RuntimeError, KeyError):
            pass
        return build_config

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build config for auth and action selection."""
        # Avoid normalizing legacy input_types here; rely on upstream fixes

        # BULLETPROOF tool_mode checking - check all possible places where tool_mode could be stored
        instance_tool_mode = getattr(self, "tool_mode", False) if hasattr(self, "tool_mode") else False

        # Check build_config for tool_mode in multiple possible structures
        build_config_tool_mode = False
        if "tool_mode" in build_config:
            tool_mode_config = build_config["tool_mode"]
            if isinstance(tool_mode_config, dict):
                build_config_tool_mode = tool_mode_config.get("value", False)
            else:
                build_config_tool_mode = bool(tool_mode_config)

        # If this is a tool_mode change, update BOTH instance variable AND build_config
        if field_name == "tool_mode":
            self.tool_mode = field_value
            instance_tool_mode = field_value
            # CRITICAL: Store tool_mode state in build_config so it persists
            if "tool_mode" not in build_config:
                build_config["tool_mode"] = {}
            if isinstance(build_config["tool_mode"], dict):
                build_config["tool_mode"]["value"] = field_value
            build_config_tool_mode = field_value

        # Current tool_mode is True if ANY source indicates it's enabled
        current_tool_mode = instance_tool_mode or build_config_tool_mode or (field_name == "tool_mode" and field_value)

        # CRITICAL: Ensure dynamic action metadata is available whenever we have an API key
        # This must happen BEFORE any early returns to ensure tools are always loaded
        api_key_available = hasattr(self, "api_key") and self.api_key

        # Check if we need to populate actions - but also check cache availability
        actions_available = bool(self._actions_data)
        toolkit_slug = getattr(self, "app_name", "").lower()
        cached_actions_available = toolkit_slug in self.__class__.get_actions_cache()

        should_populate = False

        if (field_name == "api_key" and field_value) or (
            api_key_available and not actions_available and not cached_actions_available
        ):
            should_populate = True
        elif api_key_available and not actions_available and cached_actions_available:
            self._populate_actions_data()

        if should_populate:
            logger.info(f"Populating actions data for {getattr(self, 'app_name', 'unknown')}...")
            self._populate_actions_data()
            logger.info(f"Actions populated: {len(self._actions_data)} actions found")
            # Also fetch toolkit schema to drive auth UI
            schema = self._get_toolkit_schema()
            modes = self._extract_auth_modes_from_schema(schema)
            self._render_auth_mode_dropdown(build_config, modes)
            # If a mode is selected (including auto-default), render custom fields when not managed
            try:
                selected_mode = (build_config.get("auth_mode") or {}).get("value")
                managed = (schema or {}).get("composio_managed_auth_schemes") or []
                # Don't render custom fields if "Composio_Managed" is selected
                # For API_KEY and other token modes, no fields are needed as they use link method
                token_modes = ["API_KEY", "BEARER_TOKEN", "BASIC"]
                if selected_mode and selected_mode not in ["Composio_Managed", *token_modes]:
                    self._clear_auth_dynamic_fields(build_config)
                    self._render_custom_auth_fields(build_config, schema or {}, selected_mode)
                    # Already reordered in _render_custom_auth_fields
                elif selected_mode in token_modes:
                    # Clear any existing auth fields for token-based modes
                    self._clear_auth_dynamic_fields(build_config)
            except (TypeError, ValueError, AttributeError):
                pass

        # CRITICAL: Set action options if we have actions (either from fresh population or cache)
        if self._actions_data:
            self._build_action_maps()
            build_config["action_button"]["options"] = [
                {"name": self.sanitize_action_name(action), "metadata": action} for action in self._actions_data
            ]
            logger.info(f"Action options set in build_config: {len(build_config['action_button']['options'])} options")
            # Always (re)populate auth_mode as well when actions are available
            schema = self._get_toolkit_schema()
            modes = self._extract_auth_modes_from_schema(schema)
            self._render_auth_mode_dropdown(build_config, modes)
        else:
            build_config["action_button"]["options"] = []
            logger.warning("No actions found, setting empty options")

        # clear stored connection_id when api_key is changed
        if field_name == "api_key" and field_value:
            stored_connection_before = build_config.get("auth_link", {}).get("connection_id")
            if "auth_link" in build_config and "connection_id" in build_config["auth_link"]:
                build_config["auth_link"].pop("connection_id", None)
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                logger.info(f"Cleared stored connection_id '{stored_connection_before}' due to API key change")
            else:
                logger.info("DEBUG: EARLY No stored connection_id to clear on API key change")
            # Also clear any stored scheme and reset auth mode UI when API key changes
            build_config.setdefault("auth_link", {})
            build_config["auth_link"].pop("auth_scheme", None)
            build_config.setdefault("auth_mode", {})
            build_config["auth_mode"].pop("value", None)
            build_config["auth_mode"]["show"] = True
            # If auth_mode is currently a TabInput pill, convert it back to dropdown
            if isinstance(build_config.get("auth_mode"), dict) and build_config["auth_mode"].get("type") == "tab":
                build_config["auth_mode"].pop("type", None)
            # Re-render dropdown options for the new API key context
            try:
                schema = self._get_toolkit_schema()
                modes = self._extract_auth_modes_from_schema(schema)
                # Rebuild as DropdownInput to ensure proper rendering
                dd = DropdownInput(
                    name="auth_mode",
                    display_name="Auth Mode",
                    options=modes,
                    placeholder="Select auth mode",
                    toggle=True,
                    toggle_disable=True,
                    show=True,
                    real_time_refresh=True,
                    helper_text="Choose how to authenticate with the toolkit.",
                ).to_dict()
                build_config["auth_mode"] = dd
            except (TypeError, ValueError, AttributeError):
                pass
            # NEW: Clear any selected action and hide generated fields when API key is re-entered
            try:
                if "action_button" in build_config and isinstance(build_config["action_button"], dict):
                    build_config["action_button"]["value"] = "disabled"
                self._hide_all_action_fields(build_config)
            except (TypeError, ValueError, AttributeError):
                pass

        # Handle disconnect operations when tool mode is enabled
        if field_name == "auth_link" and field_value == "disconnect":
            # Soft disconnect: do not delete remote account; only clear local state
            stored_connection_id = build_config.get("auth_link", {}).get("connection_id")
            if not stored_connection_id:
                logger.warning("No connection ID found to disconnect (soft)")
            build_config.setdefault("auth_link", {})
            build_config["auth_link"]["value"] = "connect"
            build_config["auth_link"]["auth_tooltip"] = "Connect"
            build_config["auth_link"].pop("connection_id", None)
            build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
            build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
            return self.update_input_types(build_config)

        # Handle auth mode change -> render appropriate fields based on schema
        if field_name == "auth_mode":
            schema = self._get_toolkit_schema() or {}
            # Clear any previously rendered auth fields when switching modes
            self._clear_auth_fields_from_schema(build_config, schema)
            mode = field_value if isinstance(field_value, str) else (build_config.get("auth_mode", {}).get("value"))
            if not mode and isinstance(build_config.get("auth_mode"), dict):
                mode = build_config["auth_mode"].get("value")
            # Always show auth_link for any mode
            build_config.setdefault("auth_link", {})
            build_config["auth_link"]["show"] = False
            # Reset connection state when switching modes
            build_config["auth_link"].pop("connection_id", None)
            build_config["auth_link"].pop("auth_config_id", None)
            build_config["auth_link"]["value"] = "connect"
            build_config["auth_link"]["auth_tooltip"] = "Connect"
            # If an ACTIVE connection already exists, don't render any auth fields
            existing_active = self._find_active_connection_for_app(self.app_name)
            if existing_active:
                connection_id, _ = existing_active
                self._clear_auth_fields_from_schema(build_config, schema)
                build_config.setdefault("create_auth_config", {})
                build_config["create_auth_config"]["show"] = False
                build_config["auth_link"]["value"] = "validated"
                build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                build_config["auth_link"]["connection_id"] = connection_id
                # Reflect the connected auth scheme in the UI
                scheme, _ = self._get_connection_auth_info(connection_id)
                if scheme:
                    build_config.setdefault("auth_link", {})
                    build_config["auth_link"]["auth_scheme"] = scheme
                    build_config.setdefault("auth_mode", {})
                    build_config["auth_mode"]["value"] = scheme
                    build_config["auth_mode"]["options"] = [scheme]
                    build_config["auth_mode"]["show"] = False
                    try:
                        pill = TabInput(
                            name="auth_mode",
                            display_name="Auth Mode",
                            options=[scheme],
                            value=scheme,
                        ).to_dict()
                        pill["show"] = True
                        build_config["auth_mode"] = pill
                    except (TypeError, ValueError, AttributeError):
                        build_config["auth_mode"] = {
                            "name": "auth_mode",
                            "display_name": "Auth Mode",
                            "type": "tab",
                            "options": [scheme],
                            "value": scheme,
                            "show": True,
                        }
                    build_config["action_button"]["helper_text"] = ""
                    build_config["action_button"]["helper_text_metadata"] = {}
                    return self.update_input_types(build_config)
            if mode:
                managed = schema.get("composio_managed_auth_schemes") or []
                # Always hide the Create Auth Config control (used internally only)
                build_config.setdefault("create_auth_config", {})
                build_config["create_auth_config"]["show"] = False
                build_config["create_auth_config"]["display_name"] = ""
                build_config["create_auth_config"]["value"] = ""
                build_config["create_auth_config"]["helper_text"] = ""
                build_config["create_auth_config"]["options"] = ["create"]
                if mode == "Composio_Managed":
                    # Composio_Managed → no extra fields needed
                    pass
                elif mode in ["API_KEY", "BEARER_TOKEN", "BASIC"]:
                    # Token-based modes → no fields needed, user enters on Composio page via link
                    pass
                elif isinstance(managed, list) and mode in managed:
                    # This is a specific managed auth scheme (e.g., OAUTH2) but user can still choose custom
                    # So we should render custom fields for this mode
                    self._render_custom_auth_fields(build_config, schema, mode)
                    # Already reordered in _render_custom_auth_fields
                else:
                    # Custom → render only required fields based on the toolkit schema
                    self._render_custom_auth_fields(build_config, schema, mode)
                    # Already reordered in _render_custom_auth_fields
                return self.update_input_types(build_config)

        # Handle connection initiation when tool mode is enabled
        if field_name == "auth_link" and isinstance(field_value, dict):
            try:
                toolkit_slug = self.app_name.lower()

                # First check if we already have an ACTIVE connection
                existing_active = self._find_active_connection_for_app(self.app_name)
                if existing_active:
                    connection_id, _ = existing_active
                    build_config["auth_link"]["value"] = "validated"
                    build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                    build_config["auth_link"]["connection_id"] = connection_id
                    build_config["action_button"]["helper_text"] = ""
                    build_config["action_button"]["helper_text_metadata"] = {}

                    # Clear auth fields when connected
                    schema = self._get_toolkit_schema()
                    self._clear_auth_fields_from_schema(build_config, schema)

                    # Convert auth_mode to pill for connected state
                    scheme, _ = self._get_connection_auth_info(connection_id)
                    if scheme:
                        build_config.setdefault("auth_mode", {})
                        build_config["auth_mode"]["value"] = scheme
                        build_config["auth_mode"]["options"] = [scheme]
                        build_config["auth_mode"]["show"] = False
                        try:
                            pill = TabInput(
                                name="auth_mode",
                                display_name="Auth Mode",
                                options=[scheme],
                                value=scheme,
                            ).to_dict()
                            pill["show"] = True
                            build_config["auth_mode"] = pill
                        except (TypeError, ValueError, AttributeError):
                            build_config["auth_mode"] = {
                                "name": "auth_mode",
                                "display_name": "Auth Mode",
                                "type": "tab",
                                "options": [scheme],
                                "value": scheme,
                                "show": True,
                            }

                    logger.info(f"Using existing ACTIVE connection {connection_id} for {toolkit_slug}")
                    return self.update_input_types(build_config)

                # Only reuse ACTIVE connections; otherwise create a new connection
                stored_connection_id = None

                # Create new connection ONLY if we truly have no usable connection yet
                if existing_active is None:
                    # Check if we already have a redirect URL in progress
                    current_auth_link_value = build_config.get("auth_link", {}).get("value", "")
                    if current_auth_link_value and current_auth_link_value.startswith(("http://", "https://")):
                        # We already have a redirect URL, don't create a new one
                        logger.info(f"Redirect URL already exists for {toolkit_slug}, skipping new creation")
                        return self.update_input_types(build_config)

                    try:
                        # Determine auth mode
                        schema = self._get_toolkit_schema()
                        mode = None
                        if isinstance(build_config.get("auth_mode"), dict):
                            mode = build_config["auth_mode"].get("value")
                        # If no managed default exists (400 Default auth config), require mode selection
                        managed = (schema or {}).get("composio_managed_auth_schemes") or []

                        # Handle "Composio_Managed" mode explicitly
                        if mode == "Composio_Managed":
                            # Use Composio_Managed auth flow
                            redirect_url, connection_id = self._initiate_connection(toolkit_slug)
                            build_config["auth_link"]["value"] = redirect_url
                            logger.info(f"New OAuth URL created for {toolkit_slug}: {redirect_url}")
                            return self.update_input_types(build_config)

                        if not mode:
                            build_config["auth_link"]["value"] = "connect"
                            build_config["auth_link"]["auth_tooltip"] = "Select Auth Mode"
                            return self.update_input_types(build_config)
                        # Custom modes: create auth config and/or initiate with config
                        # Only validate auth_config_creation fields for OAUTH2
                        required_missing = []
                        if mode == "OAUTH2":
                            req_names_pre = self._get_schema_field_names(
                                schema,
                                "OAUTH2",
                                "auth_config_creation",
                                "required",
                            )
                            for fname in req_names_pre:
                                if fname in build_config:
                                    val = build_config[fname].get("value")
                                    if val in (None, ""):
                                        required_missing.append(fname)
                        if required_missing:
                            # Surface errors on each missing field
                            for fname in required_missing:
                                if fname in build_config and isinstance(build_config[fname], dict):
                                    build_config[fname]["helper_text"] = "This field is required"
                                    build_config[fname]["helper_text_metadata"] = {"variant": "destructive"}
                                    # Also reflect in info for guaranteed visibility
                                    existing_info = build_config[fname].get("info") or ""
                                    build_config[fname]["info"] = f"Required: {existing_info}".strip()
                                    build_config[fname]["show"] = True
                            # Add a visible top-level hint near Auth Mode as well
                            build_config.setdefault("auth_mode", {})
                            missing_joined = ", ".join(required_missing)
                            build_config["auth_mode"]["helper_text"] = f"Missing required: {missing_joined}"
                            build_config["auth_mode"]["helper_text_metadata"] = {"variant": "destructive"}
                            build_config["auth_link"]["value"] = "connect"
                            build_config["auth_link"]["auth_tooltip"] = f"Missing: {missing_joined}"
                            return self.update_input_types(build_config)
                        composio = self._build_wrapper()
                        if mode == "OAUTH2":
                            # If an auth_config was already created via the button, use it and include initiation fields
                            stored_ac_id = (build_config.get("auth_link") or {}).get("auth_config_id")
                            if stored_ac_id:
                                # Check if we already have a redirect URL to prevent duplicates
                                current_link_value = build_config.get("auth_link", {}).get("value", "")
                                if current_link_value and current_link_value.startswith(("http://", "https://")):
                                    logger.info(
                                        f"Redirect URL already exists for {toolkit_slug} OAUTH2, skipping new creation"
                                    )
                                    return self.update_input_types(build_config)

                                # Use link method - no need to collect connection initiation fields
                                redirect = composio.connected_accounts.link(
                                    user_id=self.entity_id,
                                    auth_config_id=stored_ac_id,
                                )
                                redirect_url = getattr(redirect, "redirect_url", None)
                                connection_id = getattr(redirect, "id", None)
                                if redirect_url:
                                    build_config["auth_link"]["value"] = redirect_url
                                if connection_id:
                                    build_config["auth_link"]["connection_id"] = connection_id
                                # Clear action blocker text on successful initiation
                                build_config["action_button"]["helper_text"] = ""
                                build_config["action_button"]["helper_text_metadata"] = {}
                                # Clear any auth fields
                                schema = self._get_toolkit_schema()
                                self._clear_auth_fields_from_schema(build_config, schema)
                                return self.update_input_types(build_config)
                            # Otherwise, create custom OAuth2 auth config using schema-declared required fields
                            credentials = {}
                            missing = []
                            # Collect required names from schema
                            req_names = self._get_schema_field_names(
                                schema,
                                "OAUTH2",
                                "auth_config_creation",
                                "required",
                            )
                            candidate_names = set(self._auth_dynamic_fields) | req_names
                            for fname in candidate_names:
                                if fname in build_config:
                                    val = build_config[fname].get("value")
                                    if val not in (None, ""):
                                        credentials[fname] = val
                                    else:
                                        missing.append(fname)
                            # proceed even if missing optional; backend will validate
                            # Check if we already have a redirect URL to prevent duplicates
                            current_link_value = build_config.get("auth_link", {}).get("value", "")
                            if current_link_value and current_link_value.startswith(("http://", "https://")):
                                logger.info(
                                    f"Redirect URL already exists for {toolkit_slug} OAUTH2, skipping new creation"
                                )
                                return self.update_input_types(build_config)

                            ac = composio.auth_configs.create(
                                toolkit=toolkit_slug,
                                options={
                                    "type": "use_custom_auth",
                                    "auth_scheme": "OAUTH2",
                                    "credentials": credentials,
                                },
                            )
                            auth_config_id = getattr(ac, "id", None)
                            # Use link method directly - no need to check for connection initiation fields
                            redirect = composio.connected_accounts.link(
                                user_id=self.entity_id,
                                auth_config_id=auth_config_id,
                            )
                            redirect_url = getattr(redirect, "redirect_url", None)
                            connection_id = getattr(redirect, "id", None)
                            if redirect_url:
                                build_config["auth_link"]["value"] = redirect_url
                            if connection_id:
                                build_config["auth_link"]["connection_id"] = connection_id
                            # Hide auth fields immediately after successful initiation
                            schema = self._get_toolkit_schema()
                            self._clear_auth_fields_from_schema(build_config, schema)
                            build_config["action_button"]["helper_text"] = ""
                            build_config["action_button"]["helper_text_metadata"] = {}
                            return self.update_input_types(build_config)
                        if mode == "API_KEY":
                            # Check if we already have a redirect URL to prevent duplicates
                            current_link_value = build_config.get("auth_link", {}).get("value", "")
                            if current_link_value and current_link_value.startswith(("http://", "https://")):
                                logger.info(
                                    f"Redirect URL already exists for {toolkit_slug} API_KEY, skipping new creation"
                                )
                                return self.update_input_types(build_config)

                            ac = composio.auth_configs.create(
                                toolkit=toolkit_slug,
                                options={"type": "use_custom_auth", "auth_scheme": "API_KEY", "credentials": {}},
                            )
                            auth_config_id = getattr(ac, "id", None)
                            # Use link method - user will enter API key on Composio page
                            initiation = composio.connected_accounts.link(
                                user_id=self.entity_id,
                                auth_config_id=auth_config_id,
                            )
                            connection_id = getattr(initiation, "id", None)
                            redirect_url = getattr(initiation, "redirect_url", None)
                            # API_KEY now also returns redirect URL with new link method
                            if redirect_url:
                                build_config["auth_link"]["value"] = redirect_url
                                build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                            # Hide auth fields immediately after successful initiation
                            schema = self._get_toolkit_schema()
                            self._clear_auth_fields_from_schema(build_config, schema)
                            build_config["action_button"]["helper_text"] = ""
                            build_config["action_button"]["helper_text_metadata"] = {}

                            return self.update_input_types(build_config)
                        # Generic custom auth flow for any other mode (treat like API_KEY)
                        # Check if we already have a redirect URL to prevent duplicates
                        current_link_value = build_config.get("auth_link", {}).get("value", "")
                        if current_link_value and current_link_value.startswith(("http://", "https://")):
                            logger.info(f"Redirect URL already exists for {toolkit_slug} {mode}, skipping new creation")
                            return self.update_input_types(build_config)

                        ac = composio.auth_configs.create(
                            toolkit=toolkit_slug,
                            options={"type": "use_custom_auth", "auth_scheme": mode, "credentials": {}},
                        )
                        auth_config_id = getattr(ac, "id", None)
                        # Use link method - user will enter required fields on Composio page
                        initiation = composio.connected_accounts.link(
                            user_id=self.entity_id,
                            auth_config_id=auth_config_id,
                        )
                        connection_id = getattr(initiation, "id", None)
                        redirect_url = getattr(initiation, "redirect_url", None)
                        if redirect_url:
                            build_config["auth_link"]["value"] = redirect_url
                            build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                        # Clear auth fields
                        schema = self._get_toolkit_schema()
                        self._clear_auth_fields_from_schema(build_config, schema)
                        build_config["action_button"]["helper_text"] = ""
                        build_config["action_button"]["helper_text_metadata"] = {}
                        return self.update_input_types(build_config)
                    except (ValueError, ConnectionError, TypeError) as e:
                        logger.error(f"Error creating connection: {e}")
                        build_config["auth_link"]["value"] = "connect"
                        build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
                    else:
                        return self.update_input_types(build_config)
                else:
                    # We already have a usable connection; no new OAuth request
                    build_config["auth_link"]["auth_tooltip"] = "Disconnect"

            except (ValueError, ConnectionError) as e:
                logger.error(f"Error in connection initiation: {e}")
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
                return build_config

        # Check for ACTIVE connections and update status accordingly (tool mode)
        if hasattr(self, "api_key") and self.api_key:
            stored_connection_id = build_config.get("auth_link", {}).get("connection_id")
            active_connection_id = None

            # First try to check stored connection ID
            if stored_connection_id:
                status = self._check_connection_status_by_id(stored_connection_id)
                if status == "ACTIVE":
                    active_connection_id = stored_connection_id

            # If no stored connection or stored connection is not ACTIVE, find any ACTIVE connection
            if not active_connection_id:
                active_connection = self._find_active_connection_for_app(self.app_name)
                if active_connection:
                    active_connection_id, _ = active_connection
                    # Store the found active connection ID for future use
                    if "auth_link" not in build_config:
                        build_config["auth_link"] = {}
                    build_config["auth_link"]["connection_id"] = active_connection_id

            if active_connection_id:
                # Show validated connection status
                build_config["auth_link"]["value"] = "validated"
                build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                build_config["auth_link"]["show"] = False
                # Update auth mode UI to reflect connected scheme
                scheme, _ = self._get_connection_auth_info(active_connection_id)
                if scheme:
                    build_config.setdefault("auth_link", {})
                    build_config["auth_link"]["auth_scheme"] = scheme
                    build_config.setdefault("auth_mode", {})
                    build_config["auth_mode"]["value"] = scheme
                    build_config["auth_mode"]["options"] = [scheme]
                    build_config["auth_mode"]["show"] = False
                    try:
                        pill = TabInput(
                            name="auth_mode",
                            display_name="Auth Mode",
                            options=[scheme],
                            value=scheme,
                        ).to_dict()
                        pill["show"] = True
                        build_config["auth_mode"] = pill
                    except (TypeError, ValueError, AttributeError):
                        build_config["auth_mode"] = {
                            "name": "auth_mode",
                            "display_name": "Auth Mode",
                            "type": "tab",
                            "options": [scheme],
                            "value": scheme,
                            "show": True,
                        }
                    build_config["action_button"]["helper_text"] = ""
                    build_config["action_button"]["helper_text_metadata"] = {}
                # Clear any auth fields since we are already connected
                schema = self._get_toolkit_schema()
                self._clear_auth_fields_from_schema(build_config, schema)
                build_config.setdefault("create_auth_config", {})
                build_config["create_auth_config"]["show"] = False
                build_config["action_button"]["helper_text"] = ""
                build_config["action_button"]["helper_text_metadata"] = {}
            else:
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}

        # CRITICAL: If tool_mode is enabled from ANY source, hide action UI but keep auth flow available
        if current_tool_mode:
            build_config["action_button"]["show"] = False

            # Hide ALL action parameter fields when tool mode is enabled
            for field in self._all_fields:
                if field in build_config:
                    build_config[field]["show"] = False

            # Also hide any other action-related fields that might be in build_config
            for field_name_in_config in build_config:  # noqa: PLC0206
                # Skip base fields like api_key, tool_mode, action, etc., and dynamic auth fields
                if (
                    field_name_in_config
                    not in [
                        "api_key",
                        "tool_mode",
                        "action_button",
                        "auth_link",
                        "entity_id",
                        "auth_mode",
                        "auth_mode_pill",
                    ]
                    and field_name_in_config not in getattr(self, "_auth_dynamic_fields", set())
                    and isinstance(build_config[field_name_in_config], dict)
                    and "show" in build_config[field_name_in_config]
                ):
                    build_config[field_name_in_config]["show"] = False

            # ENSURE tool_mode state is preserved in build_config for future calls
            if "tool_mode" not in build_config:
                build_config["tool_mode"] = {"value": True}
            elif isinstance(build_config["tool_mode"], dict):
                build_config["tool_mode"]["value"] = True
            # Keep auth UI available and render fields if needed
            build_config.setdefault("auth_link", {})
            build_config["auth_link"]["show"] = False
            build_config["auth_link"]["display_name"] = ""

            # Only render auth fields if NOT already connected
            active_connection = self._find_active_connection_for_app(self.app_name)
            if not active_connection:
                try:
                    schema = self._get_toolkit_schema()
                    mode = (build_config.get("auth_mode") or {}).get("value")
                    managed = (schema or {}).get("composio_managed_auth_schemes") or []
                    token_modes = ["API_KEY", "BEARER_TOKEN", "BASIC"]
                    if (
                        mode
                        and mode not in ["Composio_Managed", *token_modes]
                        and not getattr(self, "_auth_dynamic_fields", set())
                    ):
                        self._render_custom_auth_fields(build_config, schema or {}, mode)
                        # Already reordered in _render_custom_auth_fields
                except (TypeError, ValueError, AttributeError):
                    pass
            else:
                # If connected, clear any auth fields that might be showing
                self._clear_auth_dynamic_fields(build_config)
            # Do NOT return here; allow auth flow to run in Tool Mode

        if field_name == "tool_mode":
            if field_value is True:
                build_config["action_button"]["show"] = False  # Hide action field when tool mode is enabled
                for field in self._all_fields:
                    build_config[field]["show"] = False  # Update show status for all fields based on tool mode
            elif field_value is False:
                build_config["action_button"]["show"] = True  # Show action field when tool mode is disabled
                for field in self._all_fields:
                    build_config[field]["show"] = True  # Update show status for all fields based on tool mode
            return self.update_input_types(build_config)

        if field_name == "action_button":
            # If selection is cancelled/cleared, remove generated fields
            def _is_cleared(val: Any) -> bool:
                return (
                    not val
                    or (
                        isinstance(val, list)
                        and (len(val) == 0 or (len(val) > 0 and isinstance(val[0], dict) and not val[0].get("name")))
                    )
                    or (isinstance(val, str) and val in ("", "disabled", "placeholder"))
                )

            if _is_cleared(field_value):
                self._hide_all_action_fields(build_config)
                return self.update_input_types(build_config)

            self._update_action_config(build_config, field_value)
            # Keep the existing show/hide behaviour
            self.show_hide_fields(build_config, field_value)
            return self.update_input_types(build_config)

        # Handle auth config button click
        if field_name == "create_auth_config" and field_value == "create":
            try:
                # Check if we already have a redirect URL to prevent duplicates
                current_link_value = build_config.get("auth_link", {}).get("value", "")
                if current_link_value and current_link_value.startswith(("http://", "https://")):
                    logger.info("Redirect URL already exists, skipping new auth config creation")
                    return self.update_input_types(build_config)

                composio = self._build_wrapper()
                toolkit_slug = self.app_name.lower()
                schema = self._get_toolkit_schema() or {}
                # Collect required fields from the current build_config
                credentials = {}
                req_names = self._get_schema_field_names(schema, "OAUTH2", "auth_config_creation", "required")
                candidate_names = set(self._auth_dynamic_fields) | req_names
                for fname in candidate_names:
                    if fname in build_config:
                        val = build_config[fname].get("value")
                        if val not in (None, ""):
                            credentials[fname] = val
                # Create a new auth config using the collected credentials
                ac = composio.auth_configs.create(
                    toolkit=toolkit_slug,
                    options={"type": "use_custom_auth", "auth_scheme": "OAUTH2", "credentials": credentials},
                )
                auth_config_id = getattr(ac, "id", None)
                build_config.setdefault("auth_link", {})
                if auth_config_id:
                    # Use link method directly - no need to check for connection initiation fields
                    connection_request = composio.connected_accounts.link(
                        user_id=self.entity_id, auth_config_id=auth_config_id
                    )
                    redirect_url = getattr(connection_request, "redirect_url", None)
                    connection_id = getattr(connection_request, "id", None)
                    if redirect_url and redirect_url.startswith(("http://", "https://")):
                        build_config["auth_link"]["value"] = redirect_url
                        build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                        build_config["auth_link"]["connection_id"] = connection_id
                        build_config["action_button"]["helper_text"] = ""
                        build_config["action_button"]["helper_text_metadata"] = {}
                        logger.info(f"New OAuth URL created for {toolkit_slug}: {redirect_url}")
                    else:
                        logger.error(f"Failed to initiate connection with new auth config: {redirect_url}")
                        build_config["auth_link"]["value"] = "error"
                        build_config["auth_link"]["auth_tooltip"] = f"Error: {redirect_url}"
                else:
                    logger.error(f"Failed to create new auth config for {toolkit_slug}")
                    build_config["auth_link"]["value"] = "error"
                    build_config["auth_link"]["auth_tooltip"] = "Create Auth Config failed"
            except (ValueError, ConnectionError, TypeError) as e:
                logger.error(f"Error creating new auth config: {e}")
                build_config["auth_link"]["value"] = "error"
                build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
            return self.update_input_types(build_config)

        # Handle API key removal
        if field_name == "api_key" and len(field_value) == 0:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action_button"]["options"] = []
            build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
            build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
            build_config.setdefault("auth_link", {})
            build_config["auth_link"].pop("connection_id", None)
            build_config["auth_link"].pop("auth_scheme", None)
            # Restore auth_mode dropdown and hide pill
            try:
                dd = DropdownInput(
                    name="auth_mode",
                    display_name="Auth Mode",
                    options=[],
                    placeholder="Select auth mode",
                    toggle=True,
                    toggle_disable=True,
                    show=True,
                    real_time_refresh=True,
                    helper_text="Choose how to authenticate with the toolkit.",
                ).to_dict()
                build_config["auth_mode"] = dd
            except (TypeError, ValueError, AttributeError):
                build_config.setdefault("auth_mode", {})
                build_config["auth_mode"]["show"] = True
                build_config["auth_mode"].pop("value", None)
            # NEW: Clear any selected action and hide generated fields when API key is cleared
            try:
                if "action_button" in build_config and isinstance(build_config["action_button"], dict):
                    build_config["action_button"]["value"] = "disabled"
                self._hide_all_action_fields(build_config)
            except (TypeError, ValueError, AttributeError):
                pass
            return self.update_input_types(build_config)

        # Only proceed with connection logic if we have an API key
        if not hasattr(self, "api_key") or not self.api_key:
            return self.update_input_types(build_config)

        # CRITICAL: If tool_mode is enabled (check both instance and build_config), skip all connection logic
        if current_tool_mode:
            build_config["action_button"]["show"] = False
            return self.update_input_types(build_config)

        # Update action options only if tool_mode is disabled
        self._build_action_maps()
        # Only set options if they haven't been set already during action population
        if "options" not in build_config.get("action_button", {}) or not build_config["action_button"]["options"]:
            build_config["action_button"]["options"] = [
                {"name": self.sanitize_action_name(action), "metadata": action} for action in self._actions_data
            ]
            logger.debug("Setting action options from main logic path")
        else:
            logger.debug("Action options already set, skipping duplicate setting")
        # Only set show=True if tool_mode is not enabled
        if not current_tool_mode:
            build_config["action_button"]["show"] = True

        stored_connection_id = build_config.get("auth_link", {}).get("connection_id")
        active_connection_id = None

        if stored_connection_id:
            status = self._check_connection_status_by_id(stored_connection_id)
            if status == "ACTIVE":
                active_connection_id = stored_connection_id

        if not active_connection_id:
            active_connection = self._find_active_connection_for_app(self.app_name)
            if active_connection:
                active_connection_id, _ = active_connection
                if "auth_link" not in build_config:
                    build_config["auth_link"] = {}
                build_config["auth_link"]["connection_id"] = active_connection_id

        if active_connection_id:
            build_config["auth_link"]["value"] = "validated"
            build_config["auth_link"]["auth_tooltip"] = "Disconnect"
            build_config["action_button"]["helper_text"] = ""
            build_config["action_button"]["helper_text_metadata"] = {}

            # Clear auth fields when connected
            schema = self._get_toolkit_schema()
            self._clear_auth_fields_from_schema(build_config, schema)

            # Convert auth_mode to pill for connected state
            scheme, _ = self._get_connection_auth_info(active_connection_id)
            if scheme:
                build_config.setdefault("auth_mode", {})
                build_config["auth_mode"]["value"] = scheme
                build_config["auth_mode"]["options"] = [scheme]
                build_config["auth_mode"]["show"] = False
                try:
                    pill = TabInput(
                        name="auth_mode",
                        display_name="Auth Mode",
                        options=[scheme],
                        value=scheme,
                    ).to_dict()
                    pill["show"] = True
                    build_config["auth_mode"] = pill
                except (TypeError, ValueError, AttributeError):
                    build_config["auth_mode"] = {
                        "name": "auth_mode",
                        "display_name": "Auth Mode",
                        "type": "tab",
                        "options": [scheme],
                        "value": scheme,
                        "show": True,
                    }
        elif stored_connection_id:
            status = self._check_connection_status_by_id(stored_connection_id)
            if status == "INITIATED":
                current_value = build_config.get("auth_link", {}).get("value")
                if not current_value or current_value == "connect":
                    build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
            else:
                # Connection not found or other status
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
        else:
            build_config["auth_link"]["value"] = "connect"
            build_config["auth_link"]["auth_tooltip"] = "Connect"
            build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
            build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}

        if self._is_tool_mode_enabled():
            build_config["action_button"]["show"] = False

        return self.update_input_types(build_config)

    def configure_tools(self, composio: Composio, limit: int | None = None) -> list[Tool]:
        if limit is None:
            limit = 999

        tools = composio.tools.get(user_id=self.entity_id, toolkits=[self.app_name.lower()], limit=limit)
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
        """Return tag names for actions of this app that should be exposed to the agent.

        If default tools are set via set_default_tools(), returns those.
        Otherwise, returns only the first few tools (limited by default_tools_limit)
        to prevent overwhelming the agent. Subclasses can override this behavior.

        """
        if not self._actions_data:
            self._populate_actions_data()

        if hasattr(self, "_default_tools") and self._default_tools:
            return list(self._default_tools)

        all_tools = list(self._actions_data.keys())
        limit = getattr(self, "default_tools_limit", 5)
        return all_tools[:limit]

    def execute_action(self):
        """Execute the selected Composio tool."""
        composio = self._build_wrapper()
        self._populate_actions_data()
        self._build_action_maps()

        display_name = (
            self.action_button[0]["name"]
            if isinstance(getattr(self, "action_button", None), list) and self.action_button
            else self.action_button
        )
        action_key = self._display_to_key_map.get(display_name)

        if not action_key:
            msg = f"Invalid action: {display_name}"
            raise ValueError(msg)

        try:
            arguments: dict[str, Any] = {}
            param_fields = self._actions_data.get(action_key, {}).get("action_fields", [])

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

                # Determine schema for this field
                prop_schema = schema_properties.get(field, {})

                # Parse JSON for object/array string inputs (applies to required and optional)
                if isinstance(value, str) and prop_schema.get("type") in {"array", "object"}:
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        # Fallback for simple arrays of primitives
                        if prop_schema.get("type") == "array":
                            value = [item.strip() for item in value.split(",") if item.strip() != ""]

                # For optional fields, be more strict about including them
                # Only include if the user has explicitly provided a meaningful value
                if field not in required_fields:
                    # Compare against schema default after normalization
                    schema_default = prop_schema.get("default")
                    if value == schema_default:
                        continue

                if field in self._bool_variables:
                    value = bool(value)

                # Handle renamed fields - map back to original names for API execution
                final_field_name = field
                if field.endswith("_user_id") and field.startswith(self.app_name):
                    final_field_name = "user_id"
                elif field == f"{self.app_name}_status":
                    final_field_name = "status"
                elif field == f"{self.app_name}_name":
                    final_field_name = "name"

                arguments[final_field_name] = value

            # Get the version from the action data
            version = self._actions_data.get(action_key, {}).get("version")
            if version:
                logger.info(f"Executing {action_key} with version: {version}")

            # Execute using new SDK with version parameter
            execute_params = {
                "slug": action_key,
                "arguments": arguments,
                "user_id": self.entity_id,
            }

            # Only add version if it's available
            if version:
                execute_params["version"] = version

            result = composio.tools.execute(**execute_params)

            if isinstance(result, dict) and "successful" in result:
                if result["successful"]:
                    raw_data = result.get("data", result)
                    return self._apply_post_processor(action_key, raw_data)
                error_msg = result.get("error", "Tool execution failed")
                raise ValueError(error_msg)

        except ValueError as e:
            logger.error(f"Failed to execute {action_key}: {e}")
            raise

    def _apply_post_processor(self, action_key: str, raw_data: Any) -> Any:
        """Apply post-processor for the given action if defined."""
        if hasattr(self, "post_processors") and isinstance(self.post_processors, dict):
            processor_func = self.post_processors.get(action_key)
            if processor_func and callable(processor_func):
                try:
                    return processor_func(raw_data)
                except (TypeError, ValueError, KeyError) as e:
                    logger.error(f"Error in post-processor for {action_key}: {e} (Exception type: {type(e).__name__})")
                    return raw_data

        return raw_data

    def set_default_tools(self):
        """Set the default tools."""

    def _get_schema_field_names(
        self,
        schema: dict[str, Any] | None,
        mode: str,
        section_kind: str,
        bucket: str,
    ) -> set[str]:
        names: set[str] = set()
        if not schema:
            return names
        details = schema.get("auth_config_details") or schema.get("authConfigDetails") or []
        for item in details:
            if (item.get("mode") or item.get("auth_method")) != mode:
                continue
            fields = item.get("fields") or {}
            section = (
                fields.get(section_kind)
                or fields.get(
                    "authConfigCreation" if section_kind == "auth_config_creation" else "connectedAccountInitiation"
                )
                or {}
            )
            for entry in section.get(bucket, []) or []:
                name = entry.get("name") if isinstance(entry, dict) else None
                if name:
                    names.add(name)
        return names

    def _get_schema_required_entries(
        self,
        schema: dict[str, Any] | None,
        mode: str,
        section_kind: str,
    ) -> list[dict[str, Any]]:
        if not schema:
            return []
        details = schema.get("auth_config_details") or schema.get("authConfigDetails") or []
        for item in details:
            if (item.get("mode") or item.get("auth_method")) != mode:
                continue
            fields = item.get("fields") or {}
            section = (
                fields.get(section_kind)
                or fields.get(
                    "authConfigCreation" if section_kind == "auth_config_creation" else "connectedAccountInitiation"
                )
                or {}
            )
            req = section.get("required", []) or []
            # Normalize dict-like entries
            return [entry for entry in req if isinstance(entry, dict)]
        return []

    def _hide_all_action_fields(self, build_config: dict) -> None:
        """Hide and reset all action parameter inputs, regardless of trace flags."""
        # Hide known action fields
        for fname in list(self._all_fields):
            if fname in build_config and isinstance(build_config[fname], dict):
                build_config[fname]["show"] = False
                build_config[fname]["value"] = "" if fname not in self._bool_variables else False
        # Hide any other visible, non-protected fields that look like parameters
        protected = {
            "code",
            "entity_id",
            "api_key",
            "auth_link",
            "action_button",
            "tool_mode",
            "auth_mode",
            "auth_mode_pill",
            "create_auth_config",
            # Pre-defined auth fields
            "client_id",
            "client_secret",
            "verification_token",
            "redirect_uri",
            "authorization_url",
            "token_url",
            "api_key_field",
            "generic_api_key",
            "token",
            "access_token",
            "refresh_token",
            "username",
            "password",
            "domain",
            "base_url",
            "bearer_token",
            "authorization_code",
            "scopes",
            "subdomain",
            "instance_url",
            "tenant_id",
        }
        # Add all dynamic auth fields to protected set
        protected.update(self._auth_dynamic_fields)
        # Also protect any auth fields discovered across all instances
        protected.update(self.__class__.get_all_auth_field_names())

        for key, cfg in list(build_config.items()):
            if key in protected:
                continue
            if isinstance(cfg, dict) and "show" in cfg:
                cfg["show"] = False
                if "value" in cfg:
                    cfg["value"] = ""
