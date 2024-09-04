from typing import Any, Sequence

from composio_langchain import Action, App, ComposioToolSet  # type: ignore
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import DropdownInput, MessageTextInput, MultiselectInput, SecretStrInput, StrInput


class ComposioAPIComponent(LCToolComponent):
    display_name: str = "Composio Tools"
    description: str = "Use Composio toolset to run actions with your agent"
    name = "ComposioAPI"
    icon = "Composio"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        MessageTextInput(name="entity_id", display_name="Entity ID", value="default", advanced=True),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            refresh_button=True,
            info="Refer to https://docs.composio.dev/introduction/foundations/howtos/get_api_key",
        ),
        DropdownInput(
            name="app_names",
            display_name="App Name",
            options=[app_name for app_name in App.__annotations__],
            value="",
            info="The app name to use. Please refresh after selecting app name",
            refresh_button=True,
        ),
        MultiselectInput(
            name="action_names",
            display_name="Actions to use",
            required=False,
            options=[],
            value=[],
            info="The actions to pass to agent to execute",
        ),
        StrInput(
            name="auth_status_config",
            display_name="Auth status",
            value="",
            refresh_button=True,
            info="Open link or enter api key. Then refresh button",
        ),
    ]

    def _check_for_authorization(self, app: str) -> str:
        """
        Checks if the app is authorized.

        Args:
            app (str): The app name to check authorization for.

        Returns:
            str: The authorization status.
        """
        toolset = self._build_wrapper()
        entity = toolset.client.get_entity(id=self.entity_id)
        try:
            entity.get_connection(app=app)
            return f"{app} CONNECTED"
        except Exception:
            return self._handle_authorization_failure(toolset, entity, app)

    def _handle_authorization_failure(self, toolset: ComposioToolSet, entity: Any, app: str) -> str:
        """
        Handles the authorization failure by attempting to process API key auth or initiate default connection.

        Args:
            toolset (ComposioToolSet): The toolset instance.
            entity (Any): The entity instance.
            app (str): The app name.

        Returns:
            str: The result of the authorization failure message.
        """
        try:
            auth_schemes = toolset.client.apps.get(app).auth_schemes
            if auth_schemes[0].auth_mode == "API_KEY":
                return self._process_api_key_auth(entity, app)
            else:
                return self._initiate_default_connection(entity, app)
        except Exception as exc:
            logger.error(f"Authorization error: {str(exc)}")
            return "Error"

    def _process_api_key_auth(self, entity: Any, app: str) -> str:
        """
        Processes the API key authentication.

        Args:
            entity (Any): The entity instance.
            app (str): The app name.

        Returns:
            str: The status of the API key authentication.
        """
        auth_status_config = self.auth_status_config
        is_url = "http" in auth_status_config or "https" in auth_status_config
        is_different_app = "CONNECTED" in auth_status_config and app not in auth_status_config
        is_default_api_key_message = "API Key" in auth_status_config

        if is_different_app or is_url or is_default_api_key_message:
            return "Enter API Key"
        else:
            if not is_default_api_key_message:
                entity.initiate_connection(
                    app_name=app,
                    auth_mode="API_KEY",
                    auth_config={"api_key": self.auth_status_config},
                    use_composio_auth=False,
                    force_new_integration=True,
                )
                return f"{app} CONNECTED"
            else:
                return "Enter API Key"

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def _get_connected_app_names_for_entity(self) -> list[str]:
        toolset = self._build_wrapper()
        connections = toolset.client.get_entity(id=self.entity_id).get_connections()
        return list(set(connection.appUniqueId for connection in connections))

    def _update_app_names_with_connected_status(self, build_config: dict) -> dict:
        connected_app_names = self._get_connected_app_names_for_entity()

        app_names = [
            f"{app_name}_CONNECTED" for app_name in App.__annotations__ if app_name.lower() in connected_app_names
        ]
        non_connected_app_names = [
            app_name for app_name in App.__annotations__ if app_name.lower() not in connected_app_names
        ]
        build_config["app_names"]["options"] = app_names + non_connected_app_names
        build_config["app_names"]["value"] = app_names[0] if app_names else ""
        return build_config

    def _get_normalized_app_name(self) -> str:
        return self.app_names.replace("_CONNECTED", "").replace("_connected", "")

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "api_key":
            if hasattr(self, "api_key") and self.api_key != "":
                build_config = self._update_app_names_with_connected_status(build_config)
            return build_config

        if field_name in {"app_names", "auth_status_config"}:
            if hasattr(self, "api_key") and self.api_key != "":
                build_config["auth_status_config"]["value"] = self._check_for_authorization(
                    self._get_normalized_app_name()
                )
            all_action_names = [action_name for action_name in Action.__annotations__]
            app_action_names = [
                action_name
                for action_name in all_action_names
                if action_name.lower().startswith(self._get_normalized_app_name().lower() + "_")
            ]
            build_config["action_names"]["options"] = app_action_names
            build_config["action_names"]["value"] = [app_action_names[0]] if app_action_names else [""]
        return build_config

    def build_tool(self) -> Sequence[Tool]:
        composio_toolset = self._build_wrapper()
        composio_tools = composio_toolset.get_tools(actions=self.action_names)
        return composio_tools

    def _build_wrapper(self) -> ComposioToolSet:
        return ComposioToolSet(api_key=self.api_key)
