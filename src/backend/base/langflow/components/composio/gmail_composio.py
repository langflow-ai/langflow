import json
from typing import Any

from composio import Action

from langflow.base.composio.composio_base import ComposioBaseComponent
from langflow.inputs.inputs import (
    BoolInput,
    FileInput,
    IntInput,
    MessageTextInput,
)
from langflow.logging import logger


class ComposioGmailAPIComponent(ComposioBaseComponent):
    """Gmail API component for interacting with Gmail services."""

    display_name: str = "Gmail"
    name = "GmailAPI"
    icon = "Google"
    documentation: str = "https://docs.composio.dev"
    app_name = "gmail"

    # Gmail-specific actions
    _actions_data: dict = {
        "GMAIL_SEND_EMAIL": {
            "display_name": "Send Email",
            "action_fields": [
                "recipient_email",
                "subject",
                "body",
                "cc",
                "bcc",
                "is_html",
                "gmail_user_id",
                "attachment",
            ],
        },
        "GMAIL_FETCH_EMAILS": {
            "display_name": "Fetch Emails",
            "action_fields": [
                "gmail_user_id",
                "max_results",
                "query",
                "page_token",
                "label_ids",
                "include_spam_trash",
            ],
            "get_result_field": True,
            "result_field": "messages",
        },
        "GMAIL_GET_PROFILE": {
            "display_name": "Get User Profile",
            "action_fields": ["gmail_user_id"],
        },
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID": {
            "display_name": "Get Email By ID",
            "action_fields": ["message_id", "gmail_user_id", "format"],
            "get_result_field": False,
        },
        "GMAIL_CREATE_EMAIL_DRAFT": {
            "display_name": "Create Draft Email",
            "action_fields": [
                "recipient_email",
                "subject",
                "body",
                "cc",
                "bcc",
                "is_html",
                "attachment",
                "gmail_user_id",
            ],
        },
        "GMAIL_FETCH_MESSAGE_BY_THREAD_ID": {
            "display_name": "Get Message By Thread ID",
            "action_fields": ["thread_id", "page_token", "gmail_user_id"],
            "get_result_field": False,
        },
        "GMAIL_LIST_THREADS": {
            "display_name": "List Email Threads",
            "action_fields": ["max_results", "query", "gmail_user_id", "page_token"],
            "get_result_field": True,
            "result_field": "threads",
        },
        "GMAIL_REPLY_TO_THREAD": {
            "display_name": "Reply To Thread",
            "action_fields": ["thread_id", "message_body", "recipient_email", "gmail_user_id", "cc", "bcc", "is_html"],
        },
        "GMAIL_LIST_LABELS": {
            "display_name": "List Email Labels",
            "action_fields": ["gmail_user_id"],
            "get_result_field": True,
            "result_field": "labels",
        },
        "GMAIL_CREATE_LABEL": {
            "display_name": "Create Email Label",
            "action_fields": ["label_name", "label_list_visibility", "message_list_visibility", "gmail_user_id"],
        },
        "GMAIL_GET_PEOPLE": {
            "display_name": "Get Contacts",
            "action_fields": ["resource_name", "person_fields"],
            "get_result_field": True,
            "result_field": "people_data",
        },
        "GMAIL_REMOVE_LABEL": {
            "display_name": "Delete Email Label",
            "action_fields": ["label_id", "gmail_user_id"],
            "get_result_field": False,
        },
        "GMAIL_GET_ATTACHMENT": {
            "display_name": "Get Attachment",
            "action_fields": ["message_id", "attachment_id", "file_name", "gmail_user_id"],
        },
    }
    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    _bool_variables = {"is_html", "include_spam_trash"}

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
            advanced=False,
        ),
        MessageTextInput(
            name="subject",
            display_name="Subject",
            info="Subject of the email",
            show=False,
            required=True,
            advanced=False,
        ),
        MessageTextInput(
            name="body",
            display_name="Body",
            required=True,
            info="Content of the email",
            show=False,
            advanced=False,
        ),
        MessageTextInput(
            name="cc",
            display_name="CC",
            info="Email addresses to CC (Carbon Copy) in the email, separated by commas",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="bcc",
            display_name="BCC",
            info="Email addresses to BCC (Blind Carbon Copy) in the email, separated by commas",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="is_html",
            display_name="Is HTML",
            info="Specify whether the email body contains HTML content (true/false)",
            show=False,
            value=False,
            advanced=True,
        ),
        # Email retrieval and management fields
        MessageTextInput(
            name="gmail_user_id",
            display_name="User ID",
            info="The user's email address or 'me' for the authenticated user",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            required=True,
            info="Maximum number of emails to be returned",
            show=False,
            advanced=False,
        ),
        MessageTextInput(
            name="message_id",
            display_name="Message ID",
            info="The ID of the specific email message",
            show=False,
            required=True,
            advanced=False,
        ),
        MessageTextInput(
            name="thread_id",
            display_name="Thread ID",
            info="The ID of the email thread",
            show=False,
            required=True,
            advanced=False,
        ),
        MessageTextInput(
            name="query",
            display_name="Query",
            info="Search query to filter emails (e.g., 'from:someone@email.com' or 'subject:hello')",
            show=False,
            advanced=False,
        ),
        MessageTextInput(
            name="message_body",
            display_name="Message Body",
            info="The body content of the message to be sent",
            show=False,
            advanced=True,
        ),
        # Label management fields
        MessageTextInput(
            name="label_name",
            display_name="Label Name",
            info="Name of the Gmail label to create, modify, or filter by",
            show=False,
            required=True,
            advanced=False,
        ),
        MessageTextInput(
            name="label_id",
            display_name="Label ID",
            info="The ID of the Gmail label",
            show=False,
            advanced=False,
        ),
        MessageTextInput(
            name="label_ids",
            display_name="Label Ids",
            info="Comma-separated list of label IDs to filter messages",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="label_list_visibility",
            display_name="Label List Visibility",
            info="The visibility of the label in the label list in the Gmail web interface",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="message_list_visibility",
            display_name="Message List Visibility",
            info="The visibility of the label in the message list in the Gmail web interface",
            show=False,
            advanced=True,
        ),
        # Pagination and filtering
        MessageTextInput(
            name="page_token",
            display_name="Page Token",
            info="Token for retrieving the next page of results",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="include_spam_trash",
            display_name="Include messages from Spam/Trash",
            info="Include messages from SPAM and TRASH in the results",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="format",
            display_name="Format",
            info="The format to return the message in. Possible values: minimal, full, raw, metadata",
            show=False,
            advanced=True,
        ),
        # Contact management fields
        MessageTextInput(
            name="resource_name",
            display_name="Resource Name",
            info="The resource name of the person to provide information about",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="person_fields",
            display_name="Person fields",
            info="Fields to return for the person. Multiple fields can be specified by separating them with commas",
            show=False,
            advanced=True,
        ),
        # Attachment handling
        MessageTextInput(
            name="attachment_id",
            display_name="Attachment ID",
            info="Id of the attachment",
            show=False,
            required=True,
            advanced=False,
        ),
        MessageTextInput(
            name="file_name",
            display_name="File name",
            info="File name of the attachment file",
            show=False,
            required=True,
            advanced=False,
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

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            # Get the display name from the action list
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
            # Use the display_to_key_map to get the action key
            action_key = self._display_to_key_map.get(display_name)
            if not action_key:
                msg = f"Invalid action: {display_name}"
                raise ValueError(msg)

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

            if params.get("gmail_user_id"):
                params["user_id"] = params.pop("gmail_user_id")

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                message_str = result.get("data", {}).get("message", "{}")
                try:
                    error_data = json.loads(message_str).get("error", {})
                except json.JSONDecodeError:
                    error_data = {"error": "Failed to get exact error details"}
                return {
                    "code": error_data.get("code"),
                    "message": error_data.get("message"),
                    "errors": error_data.get("errors", []),
                    "status": error_data.get("status"),
                }

            result_data = result.get("data", {})
            actions_data = self._actions_data.get(action_key, {})
            # If 'get_result_field' is True and 'result_field' is specified, extract the data
            # using 'result_field'. Otherwise, fall back to the entire 'data' field in the response.
            if actions_data.get("get_result_field") and actions_data.get("result_field"):
                result_data = result_data.get(actions_data.get("result_field"), result.get("data", []))
            if len(result_data) != 1 and not actions_data.get("result_field") and actions_data.get("get_result_field"):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
            return result_data  # noqa: TRY300
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)

    def set_default_tools(self):
        self._default_tools = {
            "GMAIL_SEND_EMAIL",
            "GMAIL_FETCH_EMAILS",
        }
