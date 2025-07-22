import json
from typing import Any

from composio import Action

from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.inputs import BoolInput, FileInput, IntInput, MessageTextInput
from lfx.logging import logger


class ComposioOutlookAPIComponent(ComposioBaseComponent):
    display_name: str = "Outlook"
    description: str = "Outlook API"
    icon = "Outlook"
    documentation: str = "https://docs.composio.dev"
    app_name = "outlook"

    _actions_data: dict = {
        "OUTLOOK_OUTLOOK_REPLY_EMAIL": {
            "display_name": "Reply To Email",
            "action_fields": [
                "OUTLOOK_OUTLOOK_REPLY_EMAIL_user_id",
                "OUTLOOK_OUTLOOK_REPLY_EMAIL_message_id",
                "OUTLOOK_OUTLOOK_REPLY_EMAIL_comment",
                "OUTLOOK_OUTLOOK_REPLY_EMAIL_cc_emails",
                "OUTLOOK_OUTLOOK_REPLY_EMAIL_bcc_emails",
            ],
            "get_result_field": False,
        },
        "OUTLOOK_OUTLOOK_GET_PROFILE": {
            "display_name": "Get Profile",
            "action_fields": ["OUTLOOK_OUTLOOK_GET_PROFILE_user_id"],
            "get_result_field": True,
            "result_field": "response_data",
        },
        "OUTLOOK_OUTLOOK_SEND_EMAIL": {
            "display_name": "Send Email",
            "action_fields": [
                "OUTLOOK_OUTLOOK_SEND_EMAIL_user_id",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_subject",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_body",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_to_email",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_to_name",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_cc_emails",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_bcc_emails",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_is_html",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_save_to_sent_items",
                "OUTLOOK_OUTLOOK_SEND_EMAIL_attachment",
            ],
            "get_result_field": False,
        },
        "OUTLOOK_OUTLOOK_LIST_MESSAGES": {
            "display_name": "List Messages",
            "action_fields": [
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_user_id",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_folder",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_top",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_skip",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_is_read",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_importance",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_gt",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_startswith",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_endswith",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_contains",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_ge",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_lt",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_le",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_from_address",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_has_attachments",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_body_preview_contains",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_gt",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_lt",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_categories",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_select",
                "OUTLOOK_OUTLOOK_LIST_MESSAGES_orderby",
            ],
            "get_result_field": True,
            "result_field": "value",
        },
        "OUTLOOK_OUTLOOK_LIST_EVENTS": {
            "display_name": "List Events",
            "action_fields": [
                "OUTLOOK_OUTLOOK_LIST_EVENTS_user_id",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_top",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_skip",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_filter",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_select",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_orderby",
                "OUTLOOK_OUTLOOK_LIST_EVENTS_timezone",
            ],
            "get_result_field": True,
            "result_field": "value",
        },
        "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT": {
            "display_name": "Create Calendar Event",
            "action_fields": [
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_user_id",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_subject",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_body",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_html",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_start_datetime",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_end_datetime",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_time_zone",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_online_meeting",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_online_meeting_provider",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_attendees_info",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_location",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_show_as",
                "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_categories",
            ],
            "get_result_field": True,
            "result_field": "response_data",
        },
        "OUTLOOK_OUTLOOK_GET_EVENT": {
            "display_name": "Get Calendar Event",
            "action_fields": ["OUTLOOK_OUTLOOK_GET_EVENT_user_id", "OUTLOOK_OUTLOOK_GET_EVENT_event_id"],
            "get_result_field": True,
            "result_field": "response_data",
        },
        "OUTLOOK_OUTLOOK_CREATE_DRAFT": {
            "display_name": "Create Email Draft",
            "action_fields": [
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_subject",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_body",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_to_recipients",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_cc_recipients",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_bcc_recipients",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_is_html",
                "OUTLOOK_OUTLOOK_CREATE_DRAFT_attachment",
            ],
            "get_result_field": True,
            "result_field": "response_data",
        },
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}

    _bool_variables = {
        "OUTLOOK_OUTLOOK_SEND_EMAIL_is_html",
        "OUTLOOK_OUTLOOK_SEND_EMAIL_save_to_sent_items",
        "OUTLOOK_OUTLOOK_CREATE_DRAFT_is_html",
        "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_html",
        "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_online_meeting",
        "OUTLOOK_OUTLOOK_LIST_MESSAGES_is_read",
        "OUTLOOK_OUTLOOK_LIST_MESSAGES_has_attachments",
    }

    _list_variables = {
        "OUTLOOK_OUTLOOK_LIST_EVENTS_select",
        "OUTLOOK_OUTLOOK_LIST_EVENTS_orderby",
        "OUTLOOK_OUTLOOK_SEND_EMAIL_cc_emails",
        "OUTLOOK_OUTLOOK_SEND_EMAIL_bcc_emails",
        "OUTLOOK_OUTLOOK_CREATE_DRAFT_to_recipients",
        "OUTLOOK_OUTLOOK_CREATE_DRAFT_cc_recipients",
        "OUTLOOK_OUTLOOK_CREATE_DRAFT_bcc_recipients",
        "OUTLOOK_OUTLOOK_REPLY_EMAIL_cc_emails",
        "OUTLOOK_OUTLOOK_REPLY_EMAIL_bcc_emails",
        "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_attendees_info",
        "OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_categories",
        "OUTLOOK_OUTLOOK_LIST_MESSAGES_categories",
        "OUTLOOK_OUTLOOK_LIST_MESSAGES_select",
        "OUTLOOK_OUTLOOK_LIST_MESSAGES_orderby",
    }

    inputs = [
        *ComposioBaseComponent.get_base_inputs(),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_user_id",
            display_name="User Id",
            info="The target user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
            advanced=True,
        ),
        IntInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_top",
            display_name="Max Results",
            info="The maximum number of events to return per request.",
            show=False,
            value=10,
        ),
        IntInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_skip",
            display_name="Skip",
            info="The number of events to skip before starting to collect results.",
            show=False,
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_filter",
            display_name="Filter",
            info="OData query string to filter results. Example: start/dateTime ge '2024-01-01T00:00:00'",
            show=False,
            value="",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_select",
            display_name="Select",
            info="List of properties to include in the response comma separated.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_orderby",
            display_name="Orderby",
            info="Properties to sort results by comma separated.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_EVENTS_timezone",
            display_name="Timezone",
            info="The timezone for event start and end times in the response.",
            show=False,
            value="UTC",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_user_id",
            display_name="User Id",
            info="The user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_subject",
            display_name="Subject",
            info="Subject of the email",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_body",
            display_name="Body",
            info="Body content of the email. Can be plain text or HTML based on is_html flag.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_to_email",
            display_name="Recipient Email",
            info="Recipient email address",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_to_name",
            display_name="To Name",
            info="Recipient display name",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_cc_emails",
            display_name="CC",
            info="List of CC recipient email addresses comma separated",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_bcc_emails",
            display_name="BCC",
            info="List of BCC recipient email addresses comma separated",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_is_html",
            display_name="Is HTML",
            info="Set to True if the body content is HTML formatted",
            show=False,
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_save_to_sent_items",
            display_name="Save To Sent Items",
            info="Whether to save the sent email to Sent Items folder.",
            show=False,
            value=True,
            advanced=True,
        ),
        FileInput(
            name="OUTLOOK_OUTLOOK_SEND_EMAIL_attachment",
            display_name="Attachment",
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
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_subject",
            display_name="Subject",
            info="Subject of the email",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_body",
            display_name="Body",
            info="Body content of the email. Can be plain text or HTML based on is_html flag",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_to_recipients",
            display_name="Recipient Email",
            info="List of recipient email addresses comma separated",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_cc_recipients",
            display_name="Cc Recipients",
            info="List of CC recipient email addresses",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_bcc_recipients",
            display_name="BCC",
            info="List of BCC recipient email addresses comma separated",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_is_html",
            display_name="Is HTML",
            info="Set to True if the body content is HTML formatted",
            show=False,
            value=False,
            advanced=True,
        ),
        FileInput(
            name="OUTLOOK_OUTLOOK_CREATE_DRAFT_attachment",
            display_name="Attachment",
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
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_GET_PROFILE_user_id",
            display_name="User Id",
            info="The user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_REPLY_EMAIL_user_id",
            display_name="User Id",
            info="The user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_REPLY_EMAIL_message_id",
            display_name="Message Id",
            info="The ID of the message to reply to. Can be obtained from OUTLOOK_LIST_MESSAGES action.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_REPLY_EMAIL_comment",
            display_name="Comment",
            info="Comment to include in the reply. Must be plain text.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_REPLY_EMAIL_cc_emails",
            display_name="CC",
            info="List of CC recipient email addresses comma separated",
            show=False,
            value=[],
            is_list=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_REPLY_EMAIL_bcc_emails",
            display_name="BCC",
            info="List of BCC recipient email addresses comma separated",
            show=False,
            value=[],
            is_list=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_user_id",
            display_name="User Id",
            info="The user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_subject",
            display_name="Subject",
            info="Subject of the event. Example: 'Team Meeting'.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_body",
            display_name="Body",
            info="Body content of the event. Can be plain text or HTML.",
            show=False,
            required=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_html",
            display_name="Is Html",
            info="Set to True if the body content should be interpreted as HTML.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_start_datetime",
            display_name="Start Datetime",
            info="Start date/time (ISO 8601). Example: '2025-01-03T10:00:00Z'.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_end_datetime",
            display_name="End Datetime",
            info="End date/time (ISO 8601). Example: '2025-01-03T11:00:00Z'.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_time_zone",
            display_name="Time Zone",
            info="Time zone (e.g., 'UTC' or 'America/Los_Angeles').",
            show=False,
            required=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_is_online_meeting",
            display_name="Is Online Meeting",
            info="Set to True to make this an online meeting and generate a Teams URL.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_online_meeting_provider",
            display_name="Online Meeting Provider",
            info="The online meeting service provider. Currently only supports 'teamsForBusiness'.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_attendees_info",
            display_name="Attendees",
            info="A list of attendee information. Only email is required for each attendee., Example: [{ 'email': 'team@example.com', 'name': 'Team', 'type': 'required' }, { 'email': 'other@example.com', 'type': 'optional' }, { 'email': 'other2@example.com' }]",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_location",
            display_name="Location",
            info="Location of the event (e.g., 'Conference Room').",
            show=False,
            value="",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_show_as",
            display_name="Show As",
            info="Status of the event: 'free', 'tentative', 'busy', or 'oof'.",
            show=False,
            value="busy",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_CALENDAR_CREATE_EVENT_categories",
            display_name="Categories",
            info="List of categories associated with the event comma separated.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_GET_EVENT_user_id",
            display_name="User Id",
            info="The user's email address or 'me' for the authenticated user.",
            show=False,
            value="me",
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_GET_EVENT_event_id",
            display_name="Event Id",
            info="The ID of the calendar event to retrieve.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_user_id",
            display_name="User Id",
            info="The target user's email address or 'me' for the authenticated user. For delegated access scenarios, this should be the email of the shared mailbox or delegated user.",  # noqa: E501
            show=False,
            value="me",
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_folder",
            display_name="Folder",
            info="",
            show=False,
            value="inbox",
            advanced=True,
        ),
        IntInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_top",
            display_name="Max Results",
            info="The maximum number of messages to return per request. Must be a positive integer between 1 and 1000.",
            show=False,
            value=10,
        ),
        IntInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_skip",
            display_name="Skip",
            info="The number of messages to skip before starting to collect results. Use for paginated responses.",
            show=False,
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_is_read",
            display_name="Is Read",
            info="Filter messages by read status. If set to False, only unread messages will be returned.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_importance",
            display_name="Importance",
            info="Filter messages by importance. For example, 'high', 'normal', or 'low'.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_subject",
            display_name="Subject",
            info="Filter messages by subject (exact match).",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_gt",
            display_name="Received Date Time Gt",
            info="Filter messages with a receivedDateTime greater than the specified value. Example: '2023-01-01T00:00:00Z'.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_startswith",
            display_name="Subject Startswith",
            info="Filter messages where the subject starts with the specified string.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_endswith",
            display_name="Subject Endswith",
            info="Filter messages where the subject ends with the specified string.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_subject_contains",
            display_name="Subject Contains",
            info="Filter messages where the subject contains the specified substring.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_ge",
            display_name="Received Date Time Ge",
            info="Filter messages with a receivedDateTime greater than or equal to the specified value.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_lt",
            display_name="Received Date Time Lt",
            info="Filter messages with a receivedDateTime less than the specified value.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_received_date_time_le",
            display_name="Received Date Time Le",
            info="Filter messages with a receivedDateTime less than or equal to the specified value.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_from_address",
            display_name="From Address",
            info="Filter messages by the sender's email address. Uses equality check on from/emailAddress/address.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_has_attachments",
            display_name="Has Attachments",
            info="Filter messages by whether they have attachments.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_body_preview_contains",
            display_name="Body Preview Contains",
            info="Filter messages where the bodyPreview contains the specified substring.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_gt",
            display_name="Sent Date Time Gt",
            info="Filter messages with a sentDateTime greater than the specified value.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_sent_date_time_lt",
            display_name="Sent Date Time Lt",
            info="Filter messages with a sentDateTime less than the specified value.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_categories",
            display_name="Categories",
            info="Filter messages by categories. Matches if the message contains any of the specified categories.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_select",
            display_name="Select",
            info="A list of properties to include in the response comma separated. Common properties: 'subject', 'from', 'toRecipients', 'receivedDateTime'.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="OUTLOOK_OUTLOOK_LIST_MESSAGES_orderby",
            display_name="Orderby",
            info="Specify properties to sort results by. For example, 'receivedDateTime desc' for newest messages first.",  # noqa: E501
            show=False,
            advanced=True,
        ),
    ]

    def execute_action(self):
        """Execute action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            self._build_action_maps()
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else self.action
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

                    if field in self._list_variables and value:
                        value = [item.strip() for item in value.split(",")]

                    if field in self._bool_variables:
                        value = bool(value)

                    param_name = field.replace(action_key + "_", "")

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            if not result.get("successful"):
                error_data = result.get("data", {})
                error_message = error_data.get("message", str(result.get("error", "Unknown Error")))

                if isinstance(error_message, str):
                    try:
                        error_obj = json.loads(error_message).get("error", {})
                        error_obj["status_code"] = error_data.get("status_code", 400)
                        return error_obj  # noqa: TRY300
                    except json.JSONDecodeError:
                        return {"error": error_message, "status_code": error_data.get("status_code", 400)}

                return error_message

            result_data = result.get("data", {})
            actions_data = self._actions_data.get(action_key, {})
            if actions_data.get("get_result_field") and actions_data.get("result_field"):
                response_data = result_data.get("response_data", {})
                if response_data and actions_data.get("result_field") in response_data:
                    result_data = response_data.get(actions_data.get("result_field"), result.get("data", []))
                else:
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
            self.sanitize_action_name("OUTLOOK_OUTLOOK_SEND_EMAIL").replace(" ", "-"),
            self.sanitize_action_name("OUTLOOK_OUTLOOK_LIST_MESSAGES").replace(" ", "-"),
        }
