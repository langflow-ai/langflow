import re
from abc import abstractmethod
from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio.exceptions import ApiKeyError
from composio_langchain import ComposioToolSet
from langchain_core.tools import Tool

from langflow.custom import Component
from langflow.inputs import (
    AuthInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
)
from langflow.io import Output
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.deps import get_shared_component_cache_service


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
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
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
            info="Select action to pass to the agent",
            helper_text="Please connect before selecting actions.",
            helper_text_metadata={"icon": "OctagonAlert", "variant": "destructive"},
            show=True,
            real_time_refresh=True,
            required=True,
            limit=1,
        ),
    ]
    _all_fields: set[str] = set()
    _bool_variables: set[str] = set()
    _actions_data: dict[str, dict[str, Any]] = {}
    _default_tools: set[str] = set()
    _readonly_actions: frozenset[str] = frozenset()
    _action_fields_cache: dict[str, set[str]] = {}
    _display_to_key_map: dict[str, str] = {}
    _key_to_display_map: dict[str, str] = {}
    _sanitized_names: dict[str, str] = {}
    _name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")

    outputs = [
        Output(name="dataFrame", display_name="DataFrame", method="as_dataframe"),
        Output(name="data", display_name="Data", method="as_data"),
        Output(name="message", display_name="Message", method="as_message"),
    ]

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self._cache_service = get_shared_component_cache_service()

    async def get_final_output(self) -> list[dict]:
        """Get the final output from cache or execute the action."""
        cache_key = f"final_output_{self._id}"
        
        # Try to get from cache first
        cached_result = await self._cache_service.get(cache_key)
        if cached_result is not None:
            return cached_result
            
        # If not in cache, execute and store
        result = self.execute_action()
        await self._cache_service.set(cache_key, result)
        return result

    async def set_final_output(self, output: list[dict]) -> None:
        """Set the final output in the cache."""
        if not output:
            output = self.execute_action()
        cache_key = f"final_output_{self._id}"
        await self._cache_service.set(cache_key, output)

    async def as_message(self) -> Message:
        """Get the output as a message."""
        result = await self.get_final_output()
        return Message(text=str(result))

    async def as_dataframe(self) -> DataFrame:
        """Get the output as a dataframe."""
        result = await self.get_final_output()
        df = DataFrame(result)
        self.status = df
        return df

    async def as_data(self) -> Data:
        """Get the output as data."""
        result = await self.get_final_output()
        return Data(results=result)

    def _build_action_maps(self):
        """Build lookup maps for action names."""
        if not self._display_to_key_map:
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

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Optimized build config updates."""
        if field_name == "tool_mode":
            build_config["action"]["show"] = not field_value
            for field in self._all_fields:
                build_config[field]["show"] = False
            return build_config

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)
            return build_config
        if field_name == "api_key" and len(field_value) == 0:
            build_config["auth_link"]["value"] = ""
            build_config["auth_link"]["auth_tooltip"] = "Please provide a valid Composio API Key."
            build_config["action"]["options"] = []
            build_config["action"]["helper_text"] = "Please connect before selecting actions."
            build_config["action"]["helper_text_metadata"] = {"icon": "OctagonAlert", "variant": "destructive"}
            return build_config
        if not hasattr(self, "api_key") or not self.api_key:
            return build_config

        # Build the action maps before using them
        self._build_action_maps()

        build_config["action"]["options"] = [
            {"name": self.sanitize_action_name(action)} for action in self._actions_data
        ]

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
                    except Exception as e:
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
            build_config["action"]["helper_text_metadata"] = {"icon": "OctagonAlert", "variant": "destructive"}
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
                    "icon": "OctagonAlert",
                    "variant": "destructive",
                }
                build_config["action"]["options"] = []
                build_config["action"]["value"] = ""
            except Exception as e:
                build_config["auth_link"]["value"] = "error"
                build_config["auth_link"]["auth_tooltip"] = "Failed to disconnect from the app."
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
            raise ValueError(f"Failed to disconnect from {app}: {e}") from e

    def configure_tools(self, toolset: ComposioToolSet) -> list[Tool]:
        tools = toolset.get_tools(actions=self._actions_data.keys())
        configured_tools = []
        for tool in tools:
            # Set the sanitized name
            tool.name = self._sanitized_names.get(tool.name, self._name_sanitizer.sub("-", tool.name))
            # Set the tags
            tool.tags = [tool.name]
            configured_tools.append(tool)
        return configured_tools

    async def _get_tools(self) -> list[Tool]:
        """Get tools with cached results and optimized name sanitization."""
        toolset = self._build_wrapper()
        return self.configure_tools(toolset)

    @property
    def enabled_tools(self):
        if not hasattr(self, "action") or not self.action:
            return list(self._default_tools)
        return list(self._default_tools.union(action["name"].replace(" ", "-") for action in self.action))

    @abstractmethod
    def execute_action(self) -> list[dict]:
        """Execute action and return response as Message."""
