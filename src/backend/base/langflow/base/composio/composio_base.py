import copy
import re
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


def _patch_graph_clean_null_input_types() -> None:
    """Monkey-patch Graph._create_vertex to clean legacy templates."""
    try:
        from langflow.graph.graph.base import Graph

        original_create_vertex = Graph._create_vertex

        def _create_vertex_with_cleanup(self, frontend_data):
            try:
                node_id: str | None = frontend_data.get("id") if isinstance(frontend_data, dict) else None
                if node_id and "Composio" in node_id:
                    template = frontend_data.get("data", {}).get("node", {}).get("template", {})
                    if isinstance(template, dict):
                        for field_cfg in template.values():
                            if isinstance(field_cfg, dict) and field_cfg.get("input_types") is None:
                                field_cfg["input_types"] = []
            except (AttributeError, TypeError, KeyError) as e:
                logger.debug(f"Composio template cleanup encountered error: {e}")

            return original_create_vertex(self, frontend_data)

        # Patch only once
        if getattr(Graph, "_composio_patch_applied", False) is False:
            Graph._create_vertex = _create_vertex_with_cleanup  # type: ignore[method-assign]
            Graph._composio_patch_applied = True  # type: ignore[attr-defined]
            logger.debug("Applied Composio template cleanup patch to Graph._create_vertex")

    except (AttributeError, TypeError) as e:
        logger.debug(f"Failed to apply Composio Graph patch: {e}")


# Apply the patch at import time
_patch_graph_clean_null_input_types()


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
        AuthInput(
            name="auth_link",
            value="",
            auth_tooltip="Please insert a valid Composio API Key.",
            show=False,
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

    def as_message(self) -> Message:
        result = self.execute_action()
        if result is None:
            return Message(text="Action execution returned no result")
        return Message(text=str(result))

    def as_dataframe(self) -> DataFrame:
        result = self.execute_action()

        if isinstance(result, dict):
            result = [result]
        return DataFrame(result)

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
        if toolkit_slug in self.__class__._actions_cache:
            # Deep-copy so that any mutation on this instance does not affect the
            # cached master copy.
            self._actions_data = copy.deepcopy(self.__class__._actions_cache[toolkit_slug])
            self._action_schemas = copy.deepcopy(self.__class__._action_schema_cache.get(toolkit_slug, {}))
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
                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                            "file_upload_fields": set(),
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
                                self._action_schemas[action_key] = tool_dict
                                self._actions_data[action_key] = {
                                    "display_name": display_name,
                                    "action_fields": [],
                                    "file_upload_fields": set(),
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
                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                                "file_upload_fields": set(),
                            }
                            continue

                        if flat_schema is None:
                            logger.warning(f"Flat schema is None for action key: {action_key}")
                            # Still add the action but with empty fields so the UI doesn't break
                            self._action_schemas[action_key] = tool_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                                "file_upload_fields": set(),
                            }
                            continue

                        # Extract field names and detect file upload fields during parsing
                        raw_action_fields = list(flat_schema.get("properties", {}).keys())
                        action_fields = []
                        attachment_related_found = False
                        file_upload_fields = set()

                        # Check original schema properties for file_uploadable fields
                        original_props = parameters_schema.get("properties", {})
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
                            # Check if this field is attachment-related
                            if clean_field.lower().startswith("attachment."):
                                attachment_related_found = True
                                continue  # Skip individual attachment fields

                            # Handle conflicting field names - rename user_id to avoid conflicts with entity_id
                            if clean_field == "user_id":
                                clean_field = f"{self.app_name}_user_id"

                            action_fields.append(clean_field)

                        # Add consolidated attachment field if we found attachment-related fields
                        if attachment_related_found:
                            action_fields.append("attachment")
                            file_upload_fields.add("attachment")  # Attachment fields are also file upload fields

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
                            "file_upload_fields": file_upload_fields,
                        }

                    except (KeyError, TypeError, ValueError) as flatten_error:
                        logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                        self._action_schemas[action_key] = tool_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                            "file_upload_fields": set(),
                        }
                        continue

                except ValueError as e:
                    logger.warning(f"Failed processing Composio tool for action {raw_tool}: {e}")

            # Helper look-ups used elsewhere
            self._all_fields = {f for d in self._actions_data.values() for f in d["action_fields"]}
            self._build_action_maps()

            # Cache actions for this toolkit so subsequent component instances
            # can reuse them without hitting the Composio API again.
            self.__class__._actions_cache[toolkit_slug] = copy.deepcopy(self._actions_data)
            self.__class__._action_schema_cache[toolkit_slug] = copy.deepcopy(self._action_schemas)

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

                # Get file upload fields from stored action data
                file_upload_fields = self._actions_data.get(action_key, {}).get("file_upload_fields", set())
                if attachment_related_fields:  # If we consolidated attachment fields
                    file_upload_fields = file_upload_fields | {"attachment"}

                for inp in result:
                    if hasattr(inp, "name") and inp.name is not None:
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

                # Ensure input_types is always a list
                if not isinstance(inp_dict.get("input_types"), list):
                    inp_dict["input_types"] = []

                inp_dict.setdefault("show", True)  # visible once action selected
                # Preserve previously entered value if user already filled something
                if inp.name in build_config:
                    existing_val = build_config[inp.name].get("value")
                    inp_dict.setdefault("value", existing_val)
                build_config[inp.name] = inp_dict

        # Ensure _all_fields includes new ones
        self._all_fields.update({i.name for i in lf_inputs if i.name is not None})

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
        """Initiate OAuth connection and return (redirect_url, connection_id)."""
        try:
            composio = self._build_wrapper()

            auth_configs = composio.auth_configs.list(toolkit_slug=app_name)
            if len(auth_configs.items) == 0:
                auth_config_id = self.create_new_auth_config(app_name)
            else:
                auth_config_id = None
                for auth_config in auth_configs.items:
                    if auth_config.auth_scheme == "OAUTH2":
                        auth_config_id = auth_config.id

                auth_config_id = auth_configs.items[0].id

            connection_request = composio.connected_accounts.initiate(
                user_id=self.entity_id, auth_config_id=auth_config_id
            )

            redirect_url = getattr(connection_request, "redirect_url", None)
            connection_id = getattr(connection_request, "id", None)

            if not redirect_url or not redirect_url.startswith(("http://", "https://")):
                msg = "Invalid redirect URL received from Composio"
                raise ValueError(msg)

            if not connection_id:
                msg = "No connection ID received from Composio"
                raise ValueError(msg)

            logger.info(f"OAuth connection initiated for {app_name}: {redirect_url} (ID: {connection_id})")
            return redirect_url, connection_id  # noqa: TRY300

        except Exception as e:
            logger.error(f"Error initiating connection for {app_name}: {e}")
            msg = f"Failed to initiate OAuth connection: {e}"
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

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build config for auth and action selection."""
        # Clean any legacy None values that may still be present
        for _fconfig in build_config.values():
            if isinstance(_fconfig, dict) and _fconfig.get("input_types") is None:
                _fconfig["input_types"] = []

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
        cached_actions_available = toolkit_slug in self.__class__._actions_cache

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

        # CRITICAL: Set action options if we have actions (either from fresh population or cache)
        if self._actions_data:
            self._build_action_maps()
            build_config["action_button"]["options"] = [
                {"name": self.sanitize_action_name(action), "metadata": action} for action in self._actions_data
            ]
            logger.info(f"Action options set in build_config: {len(build_config['action_button']['options'])} options")
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

        # Handle disconnect operations when tool mode is enabled
        if field_name == "auth_link" and field_value == "disconnect":
            try:
                # Get the specific connection ID that's currently being used
                stored_connection_id = build_config.get("auth_link", {}).get("connection_id")
                if stored_connection_id:
                    self._disconnect_specific_connection(stored_connection_id)
                else:
                    # No connection ID stored - nothing to disconnect
                    logger.warning("No connection ID found to disconnect")
                    build_config["auth_link"]["value"] = "connect"
                    build_config["auth_link"]["auth_tooltip"] = "Connect"
                    return build_config
            except (ValueError, ConnectionError) as e:
                logger.error(f"Error disconnecting: {e}")
                build_config["auth_link"]["value"] = "error"
                build_config["auth_link"]["auth_tooltip"] = f"Disconnect failed: {e!s}"
                return build_config
            else:
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["auth_link"].pop("connection_id", None)  # Clear stored connection ID
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
                return build_config

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
                    logger.info(f"Using existing ACTIVE connection {connection_id} for {toolkit_slug}")
                    return build_config

                # Check if we have a stored connection ID with INITIATED status
                stored_connection_id = build_config.get("auth_link", {}).get("connection_id")
                if stored_connection_id:
                    # Check status of existing connection
                    status = self._check_connection_status_by_id(stored_connection_id)
                    if status == "INITIATED":
                        # Get redirect URL from stored connection
                        try:
                            composio = self._build_wrapper()
                            connection = composio.connected_accounts.get(nanoid=stored_connection_id)
                            state = getattr(connection, "state", None)
                            if state and hasattr(state, "val"):
                                redirect_url = getattr(state.val, "redirect_url", None)
                                if redirect_url:
                                    build_config["auth_link"]["value"] = redirect_url
                                    logger.info(f"Reusing existing OAuth URL for {toolkit_slug}: {redirect_url}")
                                    return build_config
                        except (AttributeError, ValueError, ConnectionError) as e:
                            logger.debug(f"Could not retrieve connection {stored_connection_id}: {e}")
                            # Continue to create new connection below

                # Create new OAuth connection ONLY if we truly have no usable connection yet
                if existing_active is None and not (stored_connection_id and status in ("ACTIVE", "INITIATED")):
                    try:
                        redirect_url, connection_id = self._initiate_connection(toolkit_slug)
                        build_config["auth_link"]["value"] = redirect_url
                        build_config["auth_link"]["connection_id"] = connection_id  # Store connection ID
                        logger.info(f"New OAuth URL created for {toolkit_slug}: {redirect_url}")
                    except (ValueError, ConnectionError) as e:
                        logger.error(f"Error creating OAuth connection: {e}")
                        build_config["auth_link"]["value"] = "connect"
                        build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
                    else:
                        return build_config
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
                build_config["action_button"]["helper_text"] = ""
                build_config["action_button"]["helper_text_metadata"] = {}
            else:
                build_config["auth_link"]["value"] = "connect"
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
                build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}

        # CRITICAL: If tool_mode is enabled from ANY source, immediately hide action field and return
        if current_tool_mode:
            build_config["action_button"]["show"] = False

            # CRITICAL: Hide ALL action parameter fields when tool mode is enabled
            for field in self._all_fields:
                if field in build_config:
                    build_config[field]["show"] = False

            # Also hide any other action-related fields that might be in build_config
            for field_name_in_config in build_config:  # noqa: PLC0206
                # Skip base fields like api_key, tool_mode, action, etc.
                if (
                    field_name_in_config not in ["api_key", "tool_mode", "action_button", "auth_link", "entity_id"]
                    and isinstance(build_config[field_name_in_config], dict)
                    and "show" in build_config[field_name_in_config]
                ):
                    build_config[field_name_in_config]["show"] = False

            # ENSURE tool_mode state is preserved in build_config for future calls
            if "tool_mode" not in build_config:
                build_config["tool_mode"] = {"value": True}
            elif isinstance(build_config["tool_mode"], dict):
                build_config["tool_mode"]["value"] = True
            # Don't proceed with any other logic that might override this
            return build_config

        if field_name == "tool_mode":
            if field_value is True:
                build_config["action_button"]["show"] = False  # Hide action field when tool mode is enabled
                for field in self._all_fields:
                    build_config[field]["show"] = False  # Update show status for all fields based on tool mode
            elif field_value is False:
                build_config["action_button"]["show"] = True  # Show action field when tool mode is disabled
                for field in self._all_fields:
                    build_config[field]["show"] = True  # Update show status for all fields based on tool mode
            return build_config

        if field_name == "action_button":
            self._update_action_config(build_config, field_value)
            # Keep the existing show/hide behaviour
            self.show_hide_fields(build_config, field_value)
            return build_config

        # Handle API key removal
        if field_name == "api_key" and len(field_value) == 0:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action_button"]["options"] = []
            build_config["action_button"]["helper_text"] = "Please connect before selecting actions."
            build_config["action_button"]["helper_text_metadata"] = {"variant": "destructive"}
            build_config["auth_link"].pop("connection_id", None)
            return build_config

        # Only proceed with connection logic if we have an API key
        if not hasattr(self, "api_key") or not self.api_key:
            return build_config

        # CRITICAL: If tool_mode is enabled (check both instance and build_config), skip all connection logic
        if current_tool_mode:
            build_config["action_button"]["show"] = False
            return build_config

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

        return build_config

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

                # For optional fields, be more strict about including them
                # Only include if the user has explicitly provided a meaningful value
                if field not in required_fields:
                    # Get the default value from the schema
                    field_schema = schema_properties.get(field, {})
                    schema_default = field_schema.get("default")

                    # Skip if the current value matches the schema default
                    if value == schema_default:
                        continue

                # Convert comma-separated to list for array parameters (heuristic)
                prop_schema = schema_properties.get(field, {})
                if prop_schema.get("type") == "array" and isinstance(value, str):
                    value = [item.strip() for item in value.split(",")]

                if field in self._bool_variables:
                    value = bool(value)

                # Handle renamed fields - map back to original names for API execution
                final_field_name = field
                if field.endswith("_user_id") and field.startswith(self.app_name):
                    final_field_name = "user_id"

                arguments[final_field_name] = value

            # Execute using new SDK
            result = composio.tools.execute(
                slug=action_key,
                arguments=arguments,
                user_id=self.entity_id,
            )

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
