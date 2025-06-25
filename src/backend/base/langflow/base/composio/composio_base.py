import re
from abc import abstractmethod
from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio.exceptions import ApiKeyError
from composio_langchain import ComposioToolSet
from langchain_core.tools import Tool

from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import (
    AuthInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
    InputTypes,
)
from langflow.io import Output
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.base.mcp.util import create_input_schema_from_json_schema


class ComposioBaseComponent(Component):
    """Base class for Composio components with common functionality."""

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
    _all_fields: set[str] = set()
    _bool_variables: set[str] = set()
    _actions_data: dict[str, dict[str, Any]] = {}
    _default_tools: set[str] = set()
    _display_to_key_map: dict[str, str] = {}
    _key_to_display_map: dict[str, str] = {}
    _sanitized_names: dict[str, str] = {}
    _name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")

    # Cache for action → schema objects fetched from Composio
    _action_schemas: dict[str, Any] = {}

    outputs = [
        Output(name="dataFrame", display_name="DataFrame", method="as_dataframe"),
    ]

    # Ensure every Composio component automatically exposes the common inputs
    inputs = list(_base_inputs)

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
            
            logger.debug(f"Built action maps for {getattr(self, 'app_name', 'unknown app')}:")
            logger.debug(f"  _key_to_display_map: {self._key_to_display_map}")
            logger.debug(f"  _display_to_key_map: {self._display_to_key_map}")

    def sanitize_action_name(self, action_name: str) -> str:
        """Convert action name to display name using lookup."""
        self._build_action_maps()
        result = self._key_to_display_map.get(action_name, action_name)
        logger.debug(f"sanitize_action_name: '{action_name}' -> '{result}'")
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

    def _build_wrapper(self) -> ComposioToolSet:
        """Build the Composio toolset wrapper."""
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return ComposioToolSet(api_key=self.api_key)

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
            toolset = self._build_wrapper()
            # Fetch schemas for this app without enforcing a connection check
            from composio import App  # Local import to avoid breaking import order

            app_enum = getattr(App, self.app_name.upper(), None)
            if app_enum is None:
                logger.warning(f"App enum not found for app name: {self.app_name}")
                return

            schemas = toolset.get_action_schemas(apps=[app_enum], check_connected_accounts=False) or []

            for schema in schemas:
                try:
                    schema_dict = schema.model_dump() if hasattr(schema, "model_dump") else schema
                    if not schema_dict:
                        logger.warning(f"Schema is None or empty for action: {schema}")
                        continue

                    action_key = schema_dict.get("name")
                    if not action_key:
                        logger.warning(f"Action key is missing in schema: {schema_dict}")
                        continue

                    logger.debug(f"Processing action: {action_key}")

                    # Human-friendly display name (falls back to sanitised key)
                    raw_display_name = schema_dict.get("displayName")
                    if raw_display_name:
                        display_name = raw_display_name
                    else:
                        # Better fallback: convert GMAIL_SEND_EMAIL to "Send Email"
                        # Remove app prefix and convert to title case
                        clean_name = action_key
                        if clean_name.startswith(f"{self.app_name.upper()}_"):
                            clean_name = clean_name[len(f"{self.app_name.upper()}_"):]
                        # Convert underscores to spaces and title case
                        display_name = clean_name.replace("_", " ").title()
                    
                    logger.debug(f"Processing action {action_key}:")

                    # Build list of parameter names and track bool fields
                    parameters_schema = schema_dict.get("parameters", {})
                    if parameters_schema is None:
                        logger.warning(f"Parameters schema is None for action key: {action_key}")
                        # Still add the action but with empty fields
                        self._action_schemas[action_key] = schema_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                        }
                        continue

                    logger.debug(f"Parameters schema for {action_key}: {parameters_schema}")
                    
                    # Log the original schema structure to understand what Composio provides
                    if parameters_schema and isinstance(parameters_schema, dict):
                        props = parameters_schema.get("properties", {})
                        logger.debug(f"Original schema properties for {action_key}:")
                        for prop_name, prop_def in props.items():
                            logger.debug(f"  {prop_name}: {prop_def}")

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
                                self._action_schemas[action_key] = schema_dict
                                self._actions_data[action_key] = {
                                    "display_name": display_name,
                                    "action_fields": [],
                                }
                                continue

                        # Validate parameters_schema has required structure before flattening
                        if not parameters_schema.get("properties") and not parameters_schema.get("$defs"):
                            logger.debug(f"Parameters schema for {action_key} has no properties or $defs, creating minimal schema")
                            # Create a minimal valid schema to avoid errors
                            parameters_schema = {"type": "object", "properties": {}}

                        # Sanitize the schema before passing to flatten_schema
                        # Handle case where 'required' is explicitly None (causes "'NoneType' object is not iterable")
                        if parameters_schema.get("required") is None:
                            logger.debug(f"Sanitizing required field for {action_key}: None -> []")
                            parameters_schema = parameters_schema.copy()  # Don't modify the original
                            parameters_schema["required"] = []

                        try:
                            flat_schema = flatten_schema(parameters_schema)
                            logger.debug(f"flatten_schema returned: {flat_schema}")
                        except Exception as flatten_error:
                            logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                            logger.debug(f"Parameters schema that caused flatten error: {parameters_schema}")
                            # Still add the action but with empty fields so the UI doesn't break
                            self._action_schemas[action_key] = schema_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                            }
                            continue
                            
                        if flat_schema is None:
                            logger.warning(f"Flat schema is None for action key: {action_key}")
                            logger.debug(f"Parameters schema that resulted in None: {parameters_schema}")
                            # Still add the action but with empty fields so the UI doesn't break
                            self._action_schemas[action_key] = schema_dict
                            self._actions_data[action_key] = {
                                "display_name": display_name,
                                "action_fields": [],
                            }
                            continue

                        logger.debug(f"Flat parameters for {action_key}: {flat_schema}")

                        # Extract field names and clean them up (remove [0] suffixes)
                        raw_action_fields = list(flat_schema.get("properties", {}).keys())
                        action_fields = [field.replace("[0]", "") for field in raw_action_fields]
                        
                        logger.debug(f"Field names for {action_key}: {raw_action_fields} -> {action_fields}")

                        # Track boolean parameters so we can coerce them later
                        properties = flat_schema.get("properties", {})
                        if properties:
                            for p_name, p_schema in properties.items():
                                if isinstance(p_schema, dict) and p_schema.get("type") == "boolean":
                                    # Use cleaned field name for boolean tracking
                                    clean_field_name = p_name.replace("[0]", "")
                                    self._bool_variables.add(clean_field_name)

                        self._action_schemas[action_key] = schema_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": action_fields,
                        }
                        
                        logger.debug(f"Successfully processed action {action_key} with {len(action_fields)} fields: {action_fields}")

                    except Exception as schema_error:
                        logger.warning(f"Failed to process schema for action {action_key}: {schema_error}")
                        logger.debug(f"Schema processing error details for {action_key}:", exc_info=True)
                        # Still add the action but with empty fields so the UI doesn't break
                        self._action_schemas[action_key] = schema_dict
                        self._actions_data[action_key] = {
                            "display_name": display_name,
                            "action_fields": [],
                        }
                except Exception as e:  # pragma: no cover – schema edge-cases
                    logger.warning(f"Failed processing Composio schema for action {schema}: {e}")

            # Helper look-ups used elsewhere
            self._all_fields = {f for d in self._actions_data.values() for f in d["action_fields"]}
            self._build_action_maps()
            
            logger.debug(f"Final _actions_data for {self.app_name}:")
            for action_key, action_data in self._actions_data.items():
                logger.debug(f"  {action_key} -> display_name: '{action_data['display_name']}'")
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
            logger.debug(f"Processing schema for action key: {action_key}")
            
            parameters_schema = schema_dict.get("parameters", {})
            if parameters_schema is None:
                logger.warning(f"Parameters schema is None for action key: {action_key}")
                return []
            
            logger.debug(f"Parameters schema type for {action_key}: {type(parameters_schema)}")
            logger.debug(f"Parameters schema keys for {action_key}: {list(parameters_schema.keys()) if isinstance(parameters_schema, dict) else 'Not a dict'}")

            # Check if parameters_schema has the expected structure
            if not isinstance(parameters_schema, dict):
                logger.warning(f"Parameters schema is not a dict for action key: {action_key}, got: {type(parameters_schema)}")
                return []

            # Validate parameters_schema has required structure before flattening
            if not parameters_schema.get("properties") and not parameters_schema.get("$defs"):
                logger.debug(f"Parameters schema for {action_key} has no properties or $defs, creating minimal schema")
                # Create a minimal valid schema to avoid errors
                parameters_schema = {"type": "object", "properties": {}}

            # Sanitize the schema before passing to flatten_schema
            # Handle case where 'required' is explicitly None (causes "'NoneType' object is not iterable")
            if parameters_schema.get("required") is None:
                logger.debug(f"Sanitizing required field for {action_key}: None -> []")
                parameters_schema = parameters_schema.copy()  # Don't modify the original
                parameters_schema["required"] = []

            try:
                flat_schema = flatten_schema(parameters_schema)
                logger.debug(f"flatten_schema returned: {flat_schema}")
            except Exception as flatten_error:
                logger.error(f"flatten_schema failed for {action_key}: {flatten_error}")
                logger.debug(f"Parameters schema that caused flatten error: {parameters_schema}")
                return []
                
            if flat_schema is None:
                logger.warning(f"Flat schema is None for action key: {action_key}")
                logger.debug(f"Parameters schema that resulted in None: {parameters_schema}")
                return []
            
            logger.debug(f"Flat schema type for {action_key}: {type(flat_schema)}")
            logger.debug(f"Flat schema keys for {action_key}: {list(flat_schema.keys()) if isinstance(flat_schema, dict) else 'Not a dict'}")

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
                logger.debug(f"Flat schema for {action_key} has no properties, adding empty properties")
                flat_schema["properties"] = {}

            # Clean up field names - remove [0] suffixes from array fields
            cleaned_properties = {}
            for field_name, field_schema in flat_schema.get("properties", {}).items():
                # Remove [0] suffix from field names (e.g., "bcc[0]" -> "bcc", "cc[0]" -> "cc")
                clean_field_name = field_name.replace("[0]", "")
                cleaned_properties[clean_field_name] = field_schema
                logger.debug(f"Field name cleanup: '{field_name}' -> '{clean_field_name}'")
            
            # Update the flat schema with cleaned field names
            flat_schema["properties"] = cleaned_properties
            
            # Also update required fields to match cleaned names
            if "required" in flat_schema and flat_schema["required"]:
                cleaned_required = [field.replace("[0]", "") for field in flat_schema["required"]]
                flat_schema["required"] = cleaned_required

            input_schema = create_input_schema_from_json_schema(flat_schema)
            if input_schema is None:
                logger.warning(f"Input schema is None for action key: {action_key}")
                return []
            
            logger.debug(f"Input schema created successfully for {action_key}: {input_schema}")
            logger.debug(f"Input schema type: {type(input_schema)}")
            logger.debug(f"Input schema has model_fields: {hasattr(input_schema, 'model_fields')}")
            logger.debug(f"Input schema model_fields value: {getattr(input_schema, 'model_fields', 'NOT_FOUND')}")
            logger.debug(f"Input schema model_fields type: {type(getattr(input_schema, 'model_fields', None))}")
            
            # Additional safety check before calling schema_to_langflow_inputs
            if not hasattr(input_schema, 'model_fields'):
                logger.warning(f"Input schema for {action_key} does not have model_fields attribute")
                return []
            
            if input_schema.model_fields is None:
                logger.warning(f"Input schema model_fields is None for {action_key}")
                return []
            
            result = schema_to_langflow_inputs(input_schema)
            logger.debug(f"Schema to langflow inputs result for {action_key}: {len(result) if result else 'None/empty'}")
            
            # Set non-required fields as advanced
            if result and flat_schema.get("required"):
                required_fields_set = set(flat_schema["required"])
                for inp in result:
                    if hasattr(inp, 'name') and inp.name not in required_fields_set:
                        inp.advanced = True
                        logger.debug(f"Set field '{inp.name}' as advanced (not required)")
            elif result:
                # If no required fields specified, all fields are optional so set as advanced
                for inp in result:
                    if hasattr(inp, 'name'):
                        inp.advanced = True
                        logger.debug(f"Set field '{inp.name}' as advanced (no required list)")
            
            return result
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error generating inputs for {action_key}: {e}")
            logger.debug(f"Full exception details for {action_key}:", exc_info=True)
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
        """Optimized build config updates."""
        # Ensure dynamic action metadata is available whenever we have an API key
        if (field_name == "api_key" and field_value) or (self.api_key and not self._actions_data):
            self._populate_actions_data()

        if field_name == "tool_mode":
            build_config["action"]["show"] = not field_value
            for field in self._all_fields:
                build_config[field]["show"] = False
            return build_config

        if field_name == "action":
            # Dynamically inject parameter fields for the chosen action
            self._update_action_config(build_config, field_value)
            # Keep the existing show/hide behaviour for backwards-compat
            self.show_hide_fields(build_config, field_value)
            if build_config["auth_link"]["value"] == "validated":
                return build_config
        if field_name == "api_key" and len(field_value) == 0:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action"]["options"] = []
            build_config["action"]["helper_text"] = "Please connect before selecting actions."
            build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}
            return build_config
        if not hasattr(self, "api_key") or not self.api_key:
            return build_config

        # Build the action maps before using them
        self._build_action_maps()

        # Update the action options
        build_config["action"]["options"] = [
            {
                "name": self.sanitize_action_name(action),
                "metadata": action,
            }
            for action in self._actions_data
        ]
        
        logger.debug(f"Setting action options for {getattr(self, 'app_name', 'unknown app')}:")
        for option in build_config["action"]["options"]:
            logger.debug(f"  Option: name='{option['name']}', metadata='{option['metadata']}'")

        try:
            toolset = self._build_wrapper()
            entity = toolset.client.get_entity(id=self.entity_id)

            try:
                entity.get_connection(app=self.app_name)
                build_config["auth_link"]["value"] = "validated"
                build_config["auth_link"]["auth_tooltip"] = "Disconnect"
                build_config["action"]["helper_text"] = None
                build_config["action"]["helper_text_metadata"] = {}
            except NoItemsFound:
                auth_scheme = self._get_auth_scheme(self.app_name)
                if auth_scheme and auth_scheme.auth_mode == "OAUTH2":
                    try:
                        build_config["auth_link"]["value"] = self._initiate_default_connection(entity, self.app_name)
                        build_config["auth_link"]["auth_tooltip"] = "Connect"
                    except (ValueError, ConnectionError, ApiKeyError) as e:
                        build_config["auth_link"]["value"] = "disabled"
                        build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
                        logger.error(f"Error checking auth status: {e}")

        except (ValueError, ConnectionError) as e:
            build_config["auth_link"]["value"] = "error"
            build_config["auth_link"]["auth_tooltip"] = f"Error: {e!s}"
            logger.error(f"Error checking auth status: {e}")
        except ApiKeyError as e:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action"]["options"] = []
            build_config["action"]["value"] = ""
            build_config["action"]["helper_text"] = "Please connect before selecting actions."
            build_config["action"]["helper_text_metadata"] = {"variant": "destructive"}
            logger.error(f"Error checking auth status: {e}")

        # Handle disconnection
        if field_name == "auth_link" and field_value == "disconnect":
            try:
                for field in self._all_fields:
                    build_config[field]["show"] = False
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)
                self.disconnect_connection(entity, self.app_name)
                build_config["auth_link"]["value"] = self._initiate_default_connection(entity, self.app_name)
                build_config["auth_link"]["auth_tooltip"] = "Connect"
                build_config["action"]["helper_text"] = "Please connect before selecting actions."
                build_config["action"]["helper_text_metadata"] = {
                    "variant": "destructive",
                }
                build_config["action"]["options"] = []
                build_config["action"]["value"] = ""
            except (ValueError, ConnectionError, ApiKeyError) as e:
                build_config["auth_link"]["value"] = "error"
                build_config["auth_link"]["auth_tooltip"] = f"Failed to disconnect from the app: {e}"
                logger.error(f"Error disconnecting: {e}")
        if field_name == "auth_link" and field_value == "validated":
            build_config["action"]["helper_text"] = ""
            build_config["action"]["helper_text_metadata"] = {"icon": "Check", "variant": "success"}

        return build_config

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app."""
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except (ValueError, ConnectionError, NoItemsFound):
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def disconnect_connection(self, entity: Any, app: str) -> None:
        """Disconnect a Composio connection."""
        try:
            # Get the connection first
            connection = entity.get_connection(app=app)
            # Delete the connection using the integrations collection
            entity.client.integrations.remove(id=connection.integrationId)
        except Exception as e:
            logger.error(f"Error disconnecting from {app}: {e}")
            msg = f"Failed to disconnect from {app}: {e}"
            raise ValueError(msg) from e

    def configure_tools(self, toolset: ComposioToolSet) -> list[Tool]:
        tools = toolset.get_tools(actions=self._actions_data.keys())
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
        toolset = self._build_wrapper()
        self.set_default_tools()
        return self.configure_tools(toolset)

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

    def execute_action(self):  # noqa: C901  – the branching mirrors Composio responses
        """Execute the selected Composio action and return its raw `data` payload."""

        # Build toolset & make sure schemas are present
        toolset = self._build_wrapper()
        self._populate_actions_data()
        self._build_action_maps()

        # Resolve the action key from the UI-selected display name
        display_name = (
            self.action[0]["name"] if isinstance(getattr(self, "action", None), list) and self.action else self.action
        )
        action_key = self._display_to_key_map.get(display_name)
        
        logger.debug(f"Executing action for {getattr(self, 'app_name', 'unknown app')}:")
        logger.debug(f"  Raw self.action: {getattr(self, 'action', None)}")
        logger.debug(f"  Resolved display_name: {display_name}")
        logger.debug(f"  Mapped to action_key: {action_key}")
        logger.debug(f"  Available display_to_key_map: {self._display_to_key_map}")
        
        if not action_key:
            msg = f"Invalid action: {display_name}"
            raise ValueError(msg)

        try:
            from composio import Action as ComposioAction  # Local import to avoid global dependency at import time

            enum_name = getattr(ComposioAction, action_key)

            # Gather parameters from component inputs
            params: dict[str, Any] = {}
            param_fields = self._actions_data.get(action_key, {}).get("action_fields", [])
            
            # Get the schema for this action to check for defaults
            schema_dict = self._action_schemas.get(action_key, {})
            parameters_schema = schema_dict.get("parameters", {})
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
                        logger.debug(f"Skipping auto-generated UUID-like value for optional field '{field}': {value}")
                        continue

                # Convert comma-separated to list for array parameters (heuristic)
                prop_schema = schema_properties.get(field, {})
                if prop_schema.get("type") == "array" and isinstance(value, str):
                    value = [item.strip() for item in value.split(",")]

                if field in self._bool_variables:
                    value = bool(value)

                params[field] = value

            # Temporary special-case Gmail alias (kept for backward compatibility)
            # if params.get("gmail_user_id"):
            #     params["user_id"] = params.pop("gmail_user_id")
            
            logger.debug(f"Params: {params}")
            

            result = toolset.execute_action(action=enum_name, params=params)

            # if not result.get("successful", False):
            #     # Pass through error payload, ensure it's never None
            #     data = result.get("data", {})
            #     return data if data is not None else {}

            # # Ensure successful result data is never None
            # data = result.get("data", {})
            # return data if data is not None else {}
            return {"response": result}

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to execute {action_key}: {e}")
            raise

    @abstractmethod
    def set_default_tools(self):
        """Set the default tools."""
