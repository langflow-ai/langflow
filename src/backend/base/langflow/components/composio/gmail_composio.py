import re
from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

# from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.custom import Component
from langflow.inputs import (
    BoolInput,
    FileInput,
    IntInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    SortableListInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class ComposioGmailAPIComponent(Component):
    display_name: str = "Gmail"
    description: str = "Gmail API"
    name = "GmailAPI"
    icon = "Gmail"
    documentation: str = "https://docs.composio.dev"

    _actions_data: dict = {
        "GMAIL_SEND_EMAIL": {
            "display_name": "Send Email",
            "action_fields": ["recipient_email", "subject", "body", "cc", "bcc", "is_html"],
        },
        "GMAIL_FETCH_EMAILS": {
            "display_name": "Fetch Emails",
            "action_fields": ["max_results", "query"],
        },
        "GMAIL_GET_PROFILE": {
            "display_name": "Get User Profile",
            "action_fields": [],
        },
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID": {
            "display_name": "Get Email By ID",
            "action_fields": ["message_id"],
        },
        "GMAIL_CREATE_EMAIL_DRAFT": {
            "display_name": "Create Draft Email",
            "action_fields": ["recipient_email", "subject", "body", "cc", "bcc", "is_html"],
        },
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID": {
            "display_name": "Get Message By Thread ID",
            "action_fields": ["thread_id"],
        },
        "GMAIL_LIST_THREADS": {
            "display_name": "List Email Threads",
            "action_fields": ["max_results", "query"],
        },
        "GMAIL_REPLY_TO_THREAD": {
            "display_name": "Reply To Thread",
            "action_fields": ["thread_id", "message_body", "recipient_email"],
        },
        "GMAIL_LIST_LABELS": {
            "display_name": "List Email Labels",
            "action_fields": [],
        },
        "GMAIL_CREATE_LABEL": {
            "display_name": "Create Email Label",
            "action_fields": ["label_name"],
        },
        "GMAIL_GET_PEOPLE": {
            "display_name": "Get Contacts",
            "action_fields": [],
        },
        "GMAIL_REMOVE_LABEL": {
            "display_name": "Delete Email Label",
            "action_fields": ["label_id"],
        },
    }
    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    _bool_variables = {"is_html", "include_spam_trash"}

    # Cache for action fields mapping
    _action_fields_cache = {}
    _readonly_actions = frozenset(
        [
            "GMAIL_FETCH_EMAILS",
            "GMAIL_GET_PROFILE",
            "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
            "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
            "GMAIL_LIST_THREADS",
            "GMAIL_LIST_LABELS",
            "GMAIL_GET_PEOPLE",
        ]
    )

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
        # Non tool-mode input fields
        SortableListInput(
            name="action",
            display_name="Action",
            placeholder="Select Gmail action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
            input_types=["None"],
            limit=1,  # Limit to one selection since we only want one action at a time
        ),
        MessageTextInput(
            name="recipient_email",
            display_name="Recipient Email",
            info="Email address of the recipient",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="Subject of the email",
            show=False,
            required=True,
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
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            info="The ID of the specific email message",
            show=False,
            required=True,
        ),
        StrInput(
            name="thread_id",
            display_name="Thread ID",
            info="The ID of the email thread",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Search query to filter emails (e.g., 'from:someone@email.com' or 'subject:hello')",
            show=False,
        ),
        MessageTextInput(
            name="message_body",
            display_name="Message Body",
            info="The body content of the message to be sent",
            show=False,
        ),
        MessageTextInput(
            name="label_name",
            display_name="Label Name",
            info="Name of the Gmail label to create, modify, or filter by",
            show=False,
        ),
        MessageTextInput(
            name="label_id",
            display_name="Label ID",
            info="The ID of the Gmail label",
            show=False,
        ),
        MessageTextInput(
            name="cc",
            display_name="CC",
            info="Email addresses to CC (Carbon Copy) in the email, separated by commas",
            show=False,
        ),
        MessageTextInput(
            name="bcc",
            display_name="BCC",
            info="Email addresses to BCC (Blid Carbon Copy) in the email, separated by commas",
            show=False,
        ),
        BoolInput(
            name="is_html",
            display_name="Is HTML",
            info="Specify whether the email body contains HTML content (true/false)",
            show=False,
            value=False,
        ),
        MessageTextInput(
            name="page_token",
            display_name="Page Token",
            info="Token for retrieving the next page of results",
            show=False,
        ),
        MessageTextInput(
            name="label_ids",
            display_name="Label Ids",
            info="Comma-separated list of label IDs to filter messages",
            show=False,
        ),
        BoolInput(
            name="include_spam_trash",
            display_name="Include messages from Spam/Trash",
            info="Include messages from SPAM and TRASH in the results",
            show=False,
            value=False,
        ),
        MessageTextInput(
            name="format",
            display_name="Format",
            info="The format to return the message in. Possible values: minimal, full, raw, metadata",
            show=False,
        ),
        MessageTextInput(
            name="label_list_visibility",
            display_name="Label List Visibility",
            info="The visibility of the label in the label list in the Gmail web interface. Possible values: 'labelShow' to show the label in the label list, 'labelShowIfUnread' to show the label if there are any unread messages with that label, 'labelHide' to not show the label in the label list",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="message_list_visibility",
            display_name="Message List Visibility",
            info="The visibility of the label in the message list in the Gmail web interface. Possible values: 'show' to show the label in the message list, 'hide' to not show the label in the message list",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="resource_name",
            display_name="Resource Name",
            info="The resource name of the person to provide information about. To get information about a google account, specify 'people/account_id'",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="person_fields",
            display_name="Person fields",
            info="A field mask to restrict which fields on the person are returned. Multiple fields can be specified by separating them with commas.Valid values are: addresses, ageRanges, biographies, birthdays, calendarUrls, clientData, coverPhotos, email Addresses etc",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="attachment_id",
            display_name="Attachment ID",
            info="Id of the attachment",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="file_name",
            display_name="File name",
            info="File name of the attachment file",
            show=False,
            required=True,
        ),
        FileInput(
            name="attachment",
            display_name="Add Attachment",
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
            info="Add an attachment",
            show=False,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-compute default tools once during initialization
        self._default_tools = {
            self.sanitize_action_name("GMAIL_SEND_EMAIL").replace(" ", "-"),
            self.sanitize_action_name("GMAIL_FETCH_EMAILS").replace(" ", "-"),
        }
        # Pre-compile regex pattern
        self._name_sanitizer = re.compile(r"[^a-zA-Z0-9_-]")
        # Pre-compute sanitized action names
        self._sanitized_names = {
            action: self._name_sanitizer.sub("-", self.sanitize_action_name(action)) for action in self._actions_data
        }
        # Initialize tools cache

    def _build_action_maps(self):
        """Build lookup maps for action names."""
        if not hasattr(self, "_display_to_key_map"):
            self._display_to_key_map = {data["display_name"]: key for key, data in self._actions_data.items()}
            self._key_to_display_map = {key: data["display_name"] for key, data in self._actions_data.items()}

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

    def execute_action(self) -> Message:
        """Execute Gmail action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            # Get action key using lookup
            self._build_action_maps()
            action_key = self.action
            if action_key not in self._actions_data:
                action_key = self._display_to_key_map.get(action_key, action_key)

            enum_name = getattr(Action, action_key)
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["action_fields"]:
                    value = getattr(self, field)

                    # Skip empty values
                    if value is None or value == "":
                        continue

                    # Handle comma-separated fields that should be converted to lists
                    if field in ["cc", "bcc", "label_ids"] and value:
                        value = [item.strip() for item in value.split(",")]

                    # Handle boolean fields
                    if field in self._bool_variables:
                        value = bool(value)

                    params[field] = value

            # Execute API call
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

    def show_hide_fields(self, build_config: dict, field_value: Any):
        """Optimized field visibility updates by only modifying show values."""
        # Fast path for empty/None field_value
        if not field_value:
            # Only update show values
            for field in self._all_fields:
                build_config[field]["show"] = False
                # Only reset value if field is hidden
                if field in self._bool_variables:
                    build_config[field]["value"] = False
                else:
                    build_config[field]["value"] = ""
            return

        # Get action key efficiently
        action_key = None
        if isinstance(field_value, list) and field_value:
            action_key = self.desanitize_action_name(field_value[0]["name"])
        else:
            action_key = field_value

        # Get fields to show from cache
        fields_to_show = self._get_action_fields(action_key)

        # Only update show values
        for field in self._all_fields:
            should_show = field in fields_to_show
            if build_config[field]["show"] != should_show:  # Only update if visibility changed
                build_config[field]["show"] = should_show
                if not should_show:  # Reset value only when hiding
                    if field in self._bool_variables:
                        build_config[field]["value"] = False
                    else:
                        build_config[field]["value"] = ""

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Optimized build config updates by only modifying necessary show values."""
        # Update only show and advanced values for auth status
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False
        build_config["auth_link"]["show"] = False

        # Fast path for tool_mode updates
        if field_name == "tool_mode":
            build_config["action"]["show"] = not field_value
            # Hide all fields in tool mode
            for field in self._all_fields:
                build_config[field]["show"] = False
            return build_config

        # Handle action updates
        if field_name == "action":
            self.show_hide_fields(build_config, field_value)
            return build_config

        # Only proceed with API key validation if necessary
        if not hasattr(self, "api_key") or not self.api_key:
            return build_config
        # if field_name in ["api_key", "entity_id"]:
        #     print("Updating tools cache")
        #     self._tools_cache = self.configure_tools()
        # Update action options efficiently
        build_config["action"]["options"] = [
            {"name": self.sanitize_action_name(action)} for action in self._actions_data
        ]

        try:
            toolset = self._build_wrapper()
            entity = toolset.client.get_entity(id=self.entity_id)

            try:
                # Check connection status
                entity.get_connection(app="gmail")
                build_config["auth_status"]["value"] = "✅"
                build_config["auth_link"]["show"] = False
            except NoItemsFound:
                # Handle OAuth2 setup
                auth_scheme = self._get_auth_scheme("gmail")
                if auth_scheme and auth_scheme.auth_mode == "OAUTH2":
                    build_config["auth_link"]["show"] = True
                    build_config["auth_link"]["advanced"] = False
                    build_config["auth_link"]["value"] = self._initiate_default_connection(entity, "gmail")
                    build_config["auth_status"]["value"] = "Click link to authenticate"

        except (ValueError, ConnectionError) as e:
            build_config["auth_status"]["value"] = f"Error: {e!s}"
            logger.error(f"Error checking auth status: {e}")

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
        # Use cached default tools and only process new actions
        if not hasattr(self, "action") or not self.action:
            return list(self._default_tools)

        # Direct string manipulation instead of using sanitize_action_name for selected actions
        return list(self._default_tools.union(action["name"].replace(" ", "-") for action in self.action))
