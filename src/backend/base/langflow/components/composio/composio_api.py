# Standard library imports
from collections.abc import Sequence
from typing import Any

import requests

# Third-party imports
from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

# Local imports
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import DropdownInput, LinkInput, MessageTextInput, MultiselectInput, SecretStrInput, StrInput
from langflow.io import Output


class ComposioAPIComponent(LCToolComponent):
    display_name: str = "Composio Tools"
    description: str = "Use Composio toolset to run actions with your agent"
    name = "ComposioAPI"
    icon = "Composio"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        # Basic configuration inputs
        MessageTextInput(name="entity_id", display_name="Entity ID", value="default", advanced=True),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            info="Refer to https://docs.composio.dev/faq/api_key/api_key",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="app_names",
            display_name="App Name",
            options=[],
            value="",
            info="The app name to use. Please refresh after selecting app name",
            refresh_button=True,
            required=True,
        ),
        # Authentication-related inputs (initially hidden)
        SecretStrInput(
            name="app_credentials",
            display_name="App Credentials",
            required=False,
            dynamic=True,
            show=False,
            info="Credentials for app authentication (API Key, Password, etc)",
            load_from_db=False,
        ),
        MessageTextInput(
            name="username",
            display_name="Username",
            required=False,
            dynamic=True,
            show=False,
            info="Username for Basic authentication",
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
        ),
        MultiselectInput(
            name="action_names",
            display_name="Actions to use",
            required=True,
            options=[],
            value=[],
            info="The actions to pass to agent to execute",
            dynamic=True,
            show=False,
        ),
    ]

    outputs = [
        Output(name="tools", display_name="Tools", method="build_tool"),
    ]

    def _check_for_authorization(self, app: str) -> str:
        """Checks if the app is authorized.

        Args:
            app (str): The app name to check authorization for.

        Returns:
            str: The authorization status or URL.
        """
        toolset = self._build_wrapper()
        entity = toolset.client.get_entity(id=self.entity_id)
        try:
            # Check if user is already connected
            entity.get_connection(app=app)
        except NoItemsFound:
            # Get auth scheme for the app
            auth_scheme = self._get_auth_scheme(app)
            return self._handle_auth_by_scheme(entity, app, auth_scheme)
        except Exception:  # noqa: BLE001
            logger.exception("Authorization error")
            return "Error checking authorization"
        else:
            return f"{app} CONNECTED"

    def _get_auth_scheme(self, app_name: str) -> AppAuthScheme:
        """Get the primary auth scheme for an app.

        Args:
            app_name (str): The name of the app to get auth scheme for.

        Returns:
            AppAuthScheme: The auth scheme details.
        """
        toolset = self._build_wrapper()
        try:
            return toolset.get_auth_scheme_for_app(app=app_name.lower())
        except Exception:  # noqa: BLE001
            logger.exception(f"Error getting auth scheme for {app_name}")
            return None

    def _get_oauth_apps(self, api_key: str) -> list[str]:
        """Fetch OAuth-enabled apps from Composio API.

        Args:
            api_key (str): The Composio API key.

        Returns:
            list[str]: A list containing OAuth-enabled app names.
        """
        oauth_apps = []
        try:
            url = "https://backend.composio.dev/api/v1/apps"
            headers = {"x-api-key": api_key}
            params = {
                "includeLocal": "true",
                "additionalFields": "auth_schemes",
                "sortBy": "alphabet",
            }

            response = requests.get(url, headers=headers, params=params, timeout=20)
            data = response.json()

            for item in data.get("items", []):
                for auth_scheme in item.get("auth_schemes", []):
                    if auth_scheme.get("mode") in {"OAUTH1", "OAUTH2"}:
                        oauth_apps.append(item["key"].upper())
                        break
        except requests.RequestException as e:
            logger.error(f"Error fetching OAuth apps: {e}")
            return []
        else:
            return oauth_apps

    def _handle_auth_by_scheme(self, entity: Any, app: str, auth_scheme: AppAuthScheme) -> str:
        """Handle authentication based on the auth scheme.

        Args:
            entity (Any): The entity instance.
            app (str): The app name.
            auth_scheme (AppAuthScheme): The auth scheme details.

        Returns:
            str: The authentication status or URL.
        """
        auth_mode = auth_scheme.auth_mode

        try:
            # First check if already connected
            entity.get_connection(app=app)
        except NoItemsFound:
            # If not connected, handle new connection based on auth mode
            if auth_mode == "API_KEY":
                if hasattr(self, "app_credentials") and self.app_credentials:
                    try:
                        entity.initiate_connection(
                            app_name=app,
                            auth_mode="API_KEY",
                            auth_config={"api_key": self.app_credentials},
                            use_composio_auth=False,
                            force_new_integration=True,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Error connecting with API Key: {e}")
                        return "Invalid API Key"
                    else:
                        return f"{app} CONNECTED"
                return "Enter API Key"

            if (
                auth_mode == "BASIC"
                and hasattr(self, "username")
                and hasattr(self, "app_credentials")
                and self.username
                and self.app_credentials
            ):
                try:
                    entity.initiate_connection(
                        app_name=app,
                        auth_mode="BASIC",
                        auth_config={"username": self.username, "password": self.app_credentials},
                        use_composio_auth=False,
                        force_new_integration=True,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error connecting with Basic Auth: {e}")
                    return "Invalid credentials"
                else:
                    return f"{app} CONNECTED"
            elif auth_mode == "BASIC":
                return "Enter Username and Password"

            if auth_mode == "OAUTH2":
                try:
                    return self._initiate_default_connection(entity, app)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error initiating OAuth2: {e}")
                    return "OAuth2 initialization failed"

            return "Unsupported auth mode"
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error checking connection status: {e}")
            return f"Error: {e!s}"
        else:
            return f"{app} CONNECTED"

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def _get_connected_app_names_for_entity(self) -> list[str]:
        toolset = self._build_wrapper()
        connections = toolset.client.get_entity(id=self.entity_id).get_connections()
        return list({connection.appUniqueId for connection in connections})

    def _get_normalized_app_name(self) -> str:
        """Get app name without connection status suffix.

        Returns:
            str: Normalized app name.
        """
        return self.app_names.replace(" ✅", "").replace("_connected", "")

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        # Update the available apps options from the API
        if hasattr(self, "api_key") and self.api_key != "":
            toolset = self._build_wrapper()
            build_config["app_names"]["options"] = self._get_oauth_apps(api_key=self.api_key)

        # First, ensure all dynamic fields are hidden by default
        dynamic_fields = ["app_credentials", "username", "auth_link", "auth_status", "action_names"]
        for field in dynamic_fields:
            if field in build_config:
                if build_config[field]["value"] is None or build_config[field]["value"] == "":
                    build_config[field]["show"] = False
                    build_config[field]["advanced"] = True
                    build_config[field]["load_from_db"] = False
                else:
                    build_config[field]["show"] = True
                    build_config[field]["advanced"] = False

        if field_name == "app_names" and (not hasattr(self, "app_names") or not self.app_names):
            build_config["auth_status"]["show"] = True
            build_config["auth_status"]["value"] = "Please select an app first"
            return build_config

        if field_name == "app_names" and hasattr(self, "api_key") and self.api_key != "":
            # app_name = self._get_normalized_app_name()
            app_name = self.app_names
            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                # Always show auth_status when app is selected
                build_config["auth_status"]["show"] = True
                build_config["auth_status"]["advanced"] = False

                try:
                    # Check if already connected
                    entity.get_connection(app=app_name)
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False
                    # Show action selection for connected apps
                    build_config["action_names"]["show"] = True
                    build_config["action_names"]["advanced"] = False

                except NoItemsFound:
                    # Get auth scheme and show relevant fields
                    auth_scheme = self._get_auth_scheme(app_name)
                    auth_mode = auth_scheme.auth_mode
                    logger.info(f"Auth mode for {app_name}: {auth_mode}")

                    if auth_mode == "API_KEY":
                        build_config["app_credentials"]["show"] = True
                        build_config["app_credentials"]["advanced"] = False
                        build_config["app_credentials"]["display_name"] = "API Key"
                        build_config["auth_status"]["value"] = "Enter API Key"

                    elif auth_mode == "BASIC":
                        build_config["username"]["show"] = True
                        build_config["username"]["advanced"] = False
                        build_config["app_credentials"]["show"] = True
                        build_config["app_credentials"]["advanced"] = False
                        build_config["app_credentials"]["display_name"] = "Password"
                        build_config["auth_status"]["value"] = "Enter Username and Password"

                    elif auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, app_name)
                        build_config["auth_link"]["value"] = auth_url
                        build_config["auth_status"]["value"] = "Click link to authenticate"

                    else:
                        build_config["auth_status"]["value"] = "Unsupported auth mode"

                # Update action names if connected
                if build_config["auth_status"]["value"] == "✅":
                    all_action_names = [str(action).replace("Action.", "") for action in Action.all()]
                    app_action_names = [
                        action_name
                        for action_name in all_action_names
                        if action_name.lower().startswith(app_name.lower() + "_")
                    ]
                    if build_config["action_names"]["options"] != app_action_names:
                        build_config["action_names"]["options"] = app_action_names
                        build_config["action_names"]["value"] = [app_action_names[0]] if app_action_names else [""]

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error checking auth status: {e}, app: {app_name}")
                build_config["auth_status"]["value"] = f"Error: {e!s}"

        return build_config

    def build_tool(self) -> Sequence[Tool]:
        """Build Composio tools based on selected actions.

        Returns:
            Sequence[Tool]: List of configured Composio tools.
        """
        composio_toolset = self._build_wrapper()
        return composio_toolset.get_tools(actions=self.action_names)

    def _build_wrapper(self) -> ComposioToolSet:
        """Build the Composio toolset wrapper.

        Returns:
            ComposioToolSet: The initialized toolset.

        Raises:
            ValueError: If the API key is not found or invalid.
        """
        try:
            if not self.api_key:
                msg = "Composio API Key is required"
                raise ValueError(msg)
            return ComposioToolSet(api_key=self.api_key, entity_id=self.entity_id)
        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e
