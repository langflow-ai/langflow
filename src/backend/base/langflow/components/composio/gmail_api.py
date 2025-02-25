from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

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
    description: str = "Gmail API"
    name = "GmailAPI"
    icon = "Gmail"
    documentation: str = "https://docs.composio.dev"
    _actions_data: dict = {
        "GMAIL_SEND_EMAIL": ["recipient_email", "subject", "body"],
        "GMAIL_FETCH_EMAILS": ["max_results", "query"],
        "GMAIL_GET_PROFILE": [],
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID": ["message_id"],
        "GMAIL_CREATE_EMAIL_DRAFT": ["recipient_email", "subject", "body"],
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID": ["thread_id"],
        "GMAIL_LIST_THREADS": ["max_results", "query"],
        "GMAIL_REPLY_TO_THREAD": ["thread_id", "message_body", "recipient_email"],
        "GMAIL_LIST_LABELS": [],
        "GMAIL_CREATE_LABEL": ["label_name"],
        "GMAIL_GET_PEOPLE": [],
        "GMAIL_REMOVE_LABEL": ["label_id"],
    }

    inputs = [
        MessageTextInput(
            name="entity_id",
            display_name="Entity ID",
            value="default",
            advanced=True,
            tool_mode=True,  # Intentionally setting tool_mode=True to make this Component support both tool and non-tool functionality  # noqa: E501
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
        # Non tool-mode input fields
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="recipient_email",
            display_name="Recipient Email",
            info="Email address of the recipient",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="subject", display_name="Subject", info="Subject of the email", show=False, required=True
        ),
        MessageTextInput(
            name="body",
            display_name="Body",
            required=True,
            info="Content of the email",
            show=False,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            required=True,
            info="Maximum number of emails to be returned",
            show=False,
        ),
        StrInput(
            name="message_id",
            display_name="Message ID",
            info="The ID of the specific email message",
            show=False,
            required=True,
        ),
        StrInput(
            name="thread_id", display_name="Thread ID", info="The ID of the email thread", show=False, required=True
        ),
        StrInput(
            name="query",
            display_name="Query",
            info="Search query to filter emails (e.g., 'from:someone@email.com' or 'subject:hello')",
            show=False,
        ),
        StrInput(
            name="message_body",
            display_name="Message Body",
            info="The body content of the message to be sent",
            show=False,
        ),
        StrInput(
            name="label_name",
            display_name="Label Name",
            info="Name of the Gmail label to create, modify, or filter by",
            show=False,
        ),
        StrInput(
            name="label_id",
            display_name="Label ID",
            info="The ID of the Gmail label",
            show=False,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute Gmail action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            enum_name = getattr(Action, self.action)
            params = {}
            if self.action in self._actions_data:
                for field in self._actions_data[self.action]:
                    params[field] = getattr(self, field)

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            msg = f"Failed to execute {self.action}: {e!s}"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        all_fields = set()
        for fields in self._actions_data.values():
            all_fields.update(fields)

        for field in all_fields:
            build_config[field]["show"] = False
            build_config[field]["value"] = ""

        if field_value in self._actions_data:
            for field in self._actions_data[field_value]:
                build_config[field]["show"] = True

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False
                build_config["actions"]["show"] = True

                gmail_actions = list(self._actions_data.keys())
                build_config["actions"]["options"] = gmail_actions
                build_config["actions"]["value"] = [gmail_actions[0]]

                all_fields = set()
                for fields in self._actions_data.values():
                    all_fields.update(fields)
                for field in all_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True
                build_config["actions"]["show"] = False

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)

        if hasattr(self, "api_key") and self.api_key != "":
            build_config["action"]["options"] = list(self._actions_data.keys())
            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="gmail")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
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
