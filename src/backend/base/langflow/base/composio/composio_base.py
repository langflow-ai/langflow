import re
from abc import abstractmethod
from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool

from langflow.custom import Component
from langflow.inputs import (
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
    StrInput,
)
from langflow.io import Output
from langflow.logging import logger
from langflow.schema.message import Message


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
        LinkInput(
            name="auth_link",
            display_name="Authentication Link",
            value="",
            info="Click to authenticate with OAuth2",
            dynamic=True,
            show=False,
            placeholder="Click to authenticate",
        ),
        StrInput(
            name="auth_status",
            display_name="Auth Status",
            value="Not Connected",
            info="Current authentication status",
            dynamic=True,
            show=False,
            refresh_button=True,
        ),
        SortableListInput(
            name="action",
            display_name="Action",
            placeholder="Select action",
            options=[],
            value="",
            info="Select action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
            input_types=["None"],
            limit=1,
        ),
    ]
    _all_fields = set()
    _bool_variables = set()
    _actions_data = {}
    _default_tools = set()
    _readonly_actions = frozenset()
    _action_fields_cache = {}
    _display_to_key_map = {}
    _key_to_display_map = {}
    _sanitized_names = {}
    _name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

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

    def _get_action_fields(self, action_key: str) -> set:
        """Get fields for an action."""
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
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False
        build_config["auth_link"]["show"] = False

        if field_name == "tool_mode":
            build_config["action"]["show"] = not field_value
            for field in self._all_fields:
                build_config[field]["show"] = False
            return build_config

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)
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
                build_config["auth_status"]["value"] = "✅"
                build_config["auth_link"]["show"] = False
            except NoItemsFound:
                auth_scheme = self._get_auth_scheme(self.app_name)
                if auth_scheme and auth_scheme.auth_mode == "OAUTH2":
                    build_config["auth_link"]["show"] = True
                    build_config["auth_link"]["advanced"] = False
                    build_config["auth_link"]["value"] = self._initiate_default_connection(entity, self.app_name)
                    build_config["auth_status"]["value"] = "Click link to authenticate"

        except (ValueError, ConnectionError) as e:
            build_config["auth_status"]["value"] = f"Error: {e!s}"
            logger.error(f"Error checking auth status: {e}")

        return build_config

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app."""
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except Exception:
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def configure_tools(self, toolset: ComposioToolSet) -> list[Tool]:
        tools = toolset.get_tools(actions=self._actions_data.keys())
        return [
            tool
            for tool in tools
            if not (
                setattr(tool, "name", self._sanitized_names.get(tool.name, self._name_sanitizer.sub("-", tool.name)))
                or setattr(tool, "tags", [tool.name])
            )
        ]

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
    def execute_action(self) -> Message:
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            action_key = self.action
            if action_key not in self._actions_data:
                action_key = self._display_to_key_map.get(action_key, action_key)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    if value is None or value == "":
                        continue

                    if field in ["cc", "bcc", "label_ids"] and value:
                        value = [item.strip() for item in value.split(",")]

                    if field in self._bool_variables:
                        value = bool(value)

                    params[field] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )

            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.sanitize_action_name(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e
