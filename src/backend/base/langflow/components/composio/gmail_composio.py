from typing import Any

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs import (
    BoolInput,
    FileInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger
from langflow.schema.message import Message


class ComposioGmailAPIComponent(ComposioBaseComponent):
    """Gmail API component for interacting with Gmail services."""

    display_name: str = "Gmail"
    description: str = "Gmail API"
    name = "GmailAPI"
    icon = "Gmail"
    documentation: str = "https://docs.composio.dev"
    app_name = "gmail"

    # Gmail-specific actions
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Don't overwrite _actions_data since it's defined at class level
        # Instead, just use it to initialize other fields
        self._all_fields = {
            field for action_data in self._actions_data.values() for field in action_data["action_fields"]
        }

        self._bool_variables = {"is_html", "include_spam_trash"}
        self._default_tools = {
            self.sanitize_action_name("GMAIL_SEND_EMAIL").replace(" ", "-"),
            self.sanitize_action_name("GMAIL_FETCH_EMAILS").replace(" ", "-"),
        }
        # Build the action maps right away
        self._display_to_key_map = {data["display_name"]: key for key, data in self._actions_data.items()}
        self._key_to_display_map = {key: data["display_name"] for key, data in self._actions_data.items()}
        self._sanitized_names = {
            action: self._name_sanitizer.sub("-", self.sanitize_action_name(action)) for action in self._actions_data
        }

    # Combine base inputs with Gmail-specific inputs
    inputs = [
        *ComposioBaseComponent._base_inputs,
        # Email composition fields
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
        MessageTextInput(
            name="cc",
            display_name="CC",
            info="Email addresses to CC (Carbon Copy) in the email, separated by commas",
            show=False,
        ),
        MessageTextInput(
            name="bcc",
            display_name="BCC",
            info="Email addresses to BCC (Blind Carbon Copy) in the email, separated by commas",
            show=False,
        ),
        BoolInput(
            name="is_html",
            display_name="Is HTML",
            info="Specify whether the email body contains HTML content (true/false)",
            show=False,
            value=False,
        ),
        # Email retrieval and management fields
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
        MessageTextInput(
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
        # Label management fields
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
            name="label_ids",
            display_name="Label Ids",
            info="Comma-separated list of label IDs to filter messages",
            show=False,
        ),
        MessageTextInput(
            name="label_list_visibility",
            display_name="Label List Visibility",
            info="The visibility of the label in the label list in the Gmail web interface",
            show=False,
        ),
        MessageTextInput(
            name="message_list_visibility",
            display_name="Message List Visibility",
            info="The visibility of the label in the message list in the Gmail web interface",
            show=False,
        ),
        # Pagination and filtering
        MessageTextInput(
            name="page_token",
            display_name="Page Token",
            info="Token for retrieving the next page of results",
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
        # Contact management fields
        MessageTextInput(
            name="resource_name",
            display_name="Resource Name",
            info="The resource name of the person to provide information about",
            show=False,
        ),
        MessageTextInput(
            name="person_fields",
            display_name="Person fields",
            info="Fields to return for the person. Multiple fields can be specified by separating them with commas",
            show=False,
        ),
        # Attachment handling
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

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)
