# Third-party imports
import json
from typing import Any

import requests
from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

# Local imports
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    DropdownInput,
    IntInput,
    LinkInput,
    MessageTextInput,
    MultiselectInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class GmailAPIComponent(LCToolComponent):
    display_name: str = "Gmail"
    description: str = "Use Gmail API to send emails, create drafts, fetch emails get user profile info"
    name = "GmailAPI"
    icon = "Gmail"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,  # Enable tool mode toggle
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
        MultiselectInput(
            name="actions",
            display_name="Actions",
            required=True,
            options=[],
            value=[],
            info="The actions to pass to agent to execute",
            dynamic=True,
            show=False,
        ),
        # Non-tool mode inputs - explicitly set show=True
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to perform",
            show=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="recipient_email",
            display_name="Recipient Email",
            required=True,
            info="Email address of the recipient",
            show=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            required=True,
            info="Subject of the email",
            show=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="body",
            display_name="Body",
            required=True,
            info="Content of the email",
            show=False,
            tool_mode=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            required=True,
            info="Maximum number of emails to be returned",
            show=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Result", method="process_action"),
    ]

    def process_action(self) -> Message:
        """Process Gmail action and return result as Message."""
        toolset = self._build_wrapper()

        try:
            enum_name = getattr(Action, self.action)
            result = toolset.execute_action(
                action=enum_name,
                params={"recipient_email": self.recipient_email, "subject": self.subject, "body": self.body},
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            msg = f"Failed to execute {self.action}: {e!s}"
            raise ValueError(msg) from e

    def get_gmail_actions(self) -> list[str]:
        url = "https://backend.composio.dev/api/v2/actions/list/all"
        querystring = {"apps": "gmail"}
        headers = {"x-api-key": self.api_key}

        response = requests.request("GET", url, headers=headers, params=querystring, timeout=30)
        data = json.loads(response.text)

        return [item["enum"] for item in data["items"]]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        dynamic_fields = ["max_results", "body", "subject", "recipient_email"]
        # Always show auth status
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False
                build_config["actions"]["show"] = True

                gmail_actions = self.get_gmail_actions()

                if build_config["actions"]["options"] != gmail_actions:
                    build_config["actions"]["options"] = self.get_gmail_actions()
                    build_config["actions"]["value"] = [gmail_actions[0]]

                for field in dynamic_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True
                build_config["actions"]["show"] = False

        if field_name == "action":
            if field_value == "GMAIL_SEND_EMAIL":
                # show - email sending fields
                build_config["recipient_email"]["show"] = True
                build_config["subject"]["show"] = True
                build_config["body"]["show"] = True

                # Hide - fetch email fields
                build_config["max_results"]["show"] = False
                # clear value
                build_config["max_results"]["value"] = ""
            elif field_value == "GMAIL_FETCH_EMAILS":
                # Hide - email sending fields
                build_config["recipient_email"]["show"] = False
                build_config["subject"]["show"] = False
                build_config["body"]["show"] = False
                # clear value
                build_config["recipient_email"]["value"] = ""
                build_config["subject"]["value"] = ""
                build_config["body"]["value"] = ""

                # Show - fetch email fields
                build_config["max_results"]["show"] = True

        # Handle authentication checks if API key is present
        if hasattr(self, "api_key") and self.api_key != "":
            build_config["action"]["options"] = ["GMAIL_SEND_EMAIL", "GMAIL_FETCH_EMAILS"]
            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    # Check if already connected
                    entity.get_connection(app="gmail")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    # Handle authentication
                    auth_scheme = self._get_auth_scheme("gmail")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "gmail")
                        build_config["auth_link"]["value"] = auth_url
                        build_config["auth_status"]["value"] = "Click link to authenticate"

            except (ValueError, ConnectionError) as e:
                logger.error(f"Error checking auth status: {e}")
                build_config["auth_status"]["value"] = f"Error: {e!s}"

        return build_config

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

    def _initiate_default_connection(self, entity: Any, app: str) -> str:
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

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
            return ComposioToolSet(api_key=self.api_key)
        except ValueError as e:
            logger.error(f"Error building Composio wrapper: {e}")
            msg = "Please provide a valid Composio API Key in the component settings"
            raise ValueError(msg) from e

    async def to_toolkit(self) -> list[Tool]:
        toolset = self._build_wrapper()
        return toolset.get_tools(actions=self.actions)
