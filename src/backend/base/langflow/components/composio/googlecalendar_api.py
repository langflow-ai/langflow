from typing import Any

from composio.client.collections import AppAuthScheme
from composio.client.exceptions import NoItemsFound
from composio_langchain import Action, ComposioToolSet
from langchain_core.tools import Tool
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    LinkInput,
    MessageTextInput,
    SecretStrInput,
    StrInput,
)
from langflow.io import Output
from langflow.schema.message import Message


class GooglecalendarAPIComponent(LCToolComponent):
    display_name: str = "Google Calendar"
    description: str = "Google Calendar API"
    name = "GooglecalendarAPI"
    icon = "Googlecalendar"
    documentation: str = "https://docs.composio.dev"

    _display_to_enum_map = {
        "Update Google Event": "GOOGLECALENDAR_UPDATE_EVENT",
        "Remove Attendee From Event": "GOOGLECALENDAR_REMOVE_ATTENDEE",
        "Get Current Date And Time": "GOOGLECALENDAR_GET_CURRENT_DATE_TIME",
        "Quick Add Event": "GOOGLECALENDAR_QUICK_ADD",
        "List Google Calendars": "GOOGLECALENDAR_LIST_CALENDARS",
        "Find Event": "GOOGLECALENDAR_FIND_EVENT",
        "Create Event": "GOOGLECALENDAR_CREATE_EVENT",
        "Find Free Slots": "GOOGLECALENDAR_FIND_FREE_SLOTS",
        "Patch Calendar": "GOOGLECALENDAR_PATCH_CALENDAR",
        "Fetch Google Calendar": "GOOGLECALENDAR_GET_CALENDAR",
        "Delete Event": "GOOGLECALENDAR_DELETE_EVENT",
        "Duplicate Calendar": "GOOGLECALENDAR_DUPLICATE_CALENDAR",
    }

    _actions_data: dict = {
        "GOOGLECALENDAR_UPDATE_EVENT": {
            "display_name": "Update Google Event",
            "parameters": [
                "GOOGLECALENDAR_UPDATE_EVENT-description",
                "GOOGLECALENDAR_UPDATE_EVENT-eventType",
                "GOOGLECALENDAR_UPDATE_EVENT-create_meeting_room",
                "GOOGLECALENDAR_UPDATE_EVENT-guestsCanSeeOtherGuests",
                "GOOGLECALENDAR_UPDATE_EVENT-guestsCanInviteOthers",
                "GOOGLECALENDAR_UPDATE_EVENT-location",
                "GOOGLECALENDAR_UPDATE_EVENT-summary",
                "GOOGLECALENDAR_UPDATE_EVENT-transparency",
                "GOOGLECALENDAR_UPDATE_EVENT-visibility",
                "GOOGLECALENDAR_UPDATE_EVENT-timezone",
                "GOOGLECALENDAR_UPDATE_EVENT-recurrence",
                "GOOGLECALENDAR_UPDATE_EVENT-guests_can_modify",
                "GOOGLECALENDAR_UPDATE_EVENT-attendees",
                "GOOGLECALENDAR_UPDATE_EVENT-send_updates",
                "GOOGLECALENDAR_UPDATE_EVENT-start_datetime",
                "GOOGLECALENDAR_UPDATE_EVENT-event_duration_hour",
                "GOOGLECALENDAR_UPDATE_EVENT-event_duration_minutes",
                "GOOGLECALENDAR_UPDATE_EVENT-calendar_id",
                "GOOGLECALENDAR_UPDATE_EVENT-event_id",
            ],
        },
        "GOOGLECALENDAR_REMOVE_ATTENDEE": {
            "display_name": "Remove Attendee From Event",
            "parameters": [
                "GOOGLECALENDAR_REMOVE_ATTENDEE-calendar_id",
                "GOOGLECALENDAR_REMOVE_ATTENDEE-event_id",
                "GOOGLECALENDAR_REMOVE_ATTENDEE-attendee_email",
            ],
        },
        "GOOGLECALENDAR_GET_CURRENT_DATE_TIME": {
            "display_name": "Get Current Date And Time",
            "parameters": ["GOOGLECALENDAR_GET_CURRENT_DATE_TIME-timezone"],
        },
        "GOOGLECALENDAR_QUICK_ADD": {
            "display_name": "Quick Add Event",
            "parameters": [
                "GOOGLECALENDAR_QUICK_ADD-calendar_id",
                "GOOGLECALENDAR_QUICK_ADD-text",
                "GOOGLECALENDAR_QUICK_ADD-send_updates",
            ],
        },
        "GOOGLECALENDAR_LIST_CALENDARS": {
            "display_name": "List Google Calendars",
            "parameters": [
                "GOOGLECALENDAR_LIST_CALENDARS-max_results",
                "GOOGLECALENDAR_LIST_CALENDARS-min_access_role",
                "GOOGLECALENDAR_LIST_CALENDARS-page_token",
                "GOOGLECALENDAR_LIST_CALENDARS-show_deleted",
                "GOOGLECALENDAR_LIST_CALENDARS-show_hidden",
                "GOOGLECALENDAR_LIST_CALENDARS-sync_token",
            ],
        },
        "GOOGLECALENDAR_FIND_EVENT": {
            "display_name": "Find Event",
            "parameters": [
                "GOOGLECALENDAR_FIND_EVENT-calendar_id",
                "GOOGLECALENDAR_FIND_EVENT-query",
                "GOOGLECALENDAR_FIND_EVENT-max_results",
                "GOOGLECALENDAR_FIND_EVENT-order_by",
                "GOOGLECALENDAR_FIND_EVENT-show_deleted",
                "GOOGLECALENDAR_FIND_EVENT-single_events",
                "GOOGLECALENDAR_FIND_EVENT-timeMax",
                "GOOGLECALENDAR_FIND_EVENT-timeMin",
                "GOOGLECALENDAR_FIND_EVENT-updated_min",
                "GOOGLECALENDAR_FIND_EVENT-event_types",
                "GOOGLECALENDAR_FIND_EVENT-page_token",
            ],
        },
        "GOOGLECALENDAR_CREATE_EVENT": {
            "display_name": "Create Event",
            "parameters": [
                "GOOGLECALENDAR_CREATE_EVENT-description",
                "GOOGLECALENDAR_CREATE_EVENT-eventType",
                "GOOGLECALENDAR_CREATE_EVENT-create_meeting_room",
                "GOOGLECALENDAR_CREATE_EVENT-guestsCanSeeOtherGuests",
                "GOOGLECALENDAR_CREATE_EVENT-guestsCanInviteOthers",
                "GOOGLECALENDAR_CREATE_EVENT-location",
                "GOOGLECALENDAR_CREATE_EVENT-summary",
                "GOOGLECALENDAR_CREATE_EVENT-transparency",
                "GOOGLECALENDAR_CREATE_EVENT-visibility",
                "GOOGLECALENDAR_CREATE_EVENT-timezone",
                "GOOGLECALENDAR_CREATE_EVENT-recurrence",
                "GOOGLECALENDAR_CREATE_EVENT-guests_can_modify",
                "GOOGLECALENDAR_CREATE_EVENT-attendees",
                "GOOGLECALENDAR_CREATE_EVENT-send_updates",
                "GOOGLECALENDAR_CREATE_EVENT-start_datetime",
                "GOOGLECALENDAR_CREATE_EVENT-event_duration_hour",
                "GOOGLECALENDAR_CREATE_EVENT-event_duration_minutes",
                "GOOGLECALENDAR_CREATE_EVENT-calendar_id",
            ],
        },
        "GOOGLECALENDAR_FIND_FREE_SLOTS": {
            "display_name": "Find Free Slots",
            "parameters": [
                "GOOGLECALENDAR_FIND_FREE_SLOTS-time_min",
                "GOOGLECALENDAR_FIND_FREE_SLOTS-time_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS-timezone",
                "GOOGLECALENDAR_FIND_FREE_SLOTS-group_expansion_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS-calendar_expansion_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS-items",
            ],
        },
        "GOOGLECALENDAR_PATCH_CALENDAR": {
            "display_name": "Patch Calendar",
            "parameters": [
                "GOOGLECALENDAR_PATCH_CALENDAR-calendar_id",
                "GOOGLECALENDAR_PATCH_CALENDAR-description",
                "GOOGLECALENDAR_PATCH_CALENDAR-location",
                "GOOGLECALENDAR_PATCH_CALENDAR-summary",
                "GOOGLECALENDAR_PATCH_CALENDAR-timezone",
            ],
        },
        "GOOGLECALENDAR_GET_CALENDAR": {
            "display_name": "Fetch Google Calendar",
            "parameters": ["GOOGLECALENDAR_GET_CALENDAR-calendar_id"],
        },
        "GOOGLECALENDAR_DELETE_EVENT": {
            "display_name": "Delete Event",
            "parameters": ["GOOGLECALENDAR_DELETE_EVENT-calendar_id", "GOOGLECALENDAR_DELETE_EVENT-event_id"],
        },
        "GOOGLECALENDAR_DUPLICATE_CALENDAR": {
            "display_name": "Duplicate Calendar",
            "parameters": ["GOOGLECALENDAR_DUPLICATE_CALENDAR-summary"],
        },
    }

    _bool_variables = {
        "GOOGLECALENDAR_LIST_CALENDARS-show_deleted",
        "GOOGLECALENDAR_LIST_CALENDARS-show_hidden",
        "GOOGLECALENDAR_FIND_EVENT-show_deleted",
        "GOOGLECALENDAR_FIND_EVENT-single_events",
        "GOOGLECALENDAR_CREATE_EVENT-create_meeting_room",
        "GOOGLECALENDAR_CREATE_EVENT-guestsCanSeeOtherGuests",
        "GOOGLECALENDAR_CREATE_EVENT-guestsCanInviteOthers",
        "GOOGLECALENDAR_CREATE_EVENT-guests_can_modify",
        "GOOGLECALENDAR_CREATE_EVENT-send_updates",
        "GOOGLECALENDAR_UPDATE_EVENT-create_meeting_room",
        "GOOGLECALENDAR_UPDATE_EVENT-guestsCanSeeOtherGuests",
        "GOOGLECALENDAR_UPDATE_EVENT-guestsCanInviteOthers",
        "GOOGLECALENDAR_UPDATE_EVENT-guests_can_modify",
        "GOOGLECALENDAR_UPDATE_EVENT-send_updates",
    }

    _list_variables = {
        "GOOGLECALENDAR_FIND_EVENT-event_types",
        "GOOGLECALENDAR_CREATE_EVENT-recurrence",
        "GOOGLECALENDAR_CREATE_EVENT-attendees",
        "GOOGLECALENDAR_FIND_FREE_SLOTS-items",
        "GOOGLECALENDAR_UPDATE_EVENT-recurrence",
        "GOOGLECALENDAR_UPDATE_EVENT-attendees",
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
        # Non tool-mode input fields
        DropdownInput(
            name="action",
            display_name="Action",
            options=[],
            value="",
            info="Select Gmail action to pass to the agent",
            show=True,
            real_time_refresh=True,
            required=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-max_results",
            display_name="Max Results",
            info="Maximum number of entries returned on one result page. The page size can never be larger than 250 entries.",  # noqa: E501
            show=False,
            value=10,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-min_access_role",
            display_name="Min Access Role",
            info="The minimum access role for the user in the returned entries. Accepted values are 'owner' & 'reader'",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-page_token",
            display_name="Page Token",
            info="Token specifying which result page to return.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-show_deleted",
            display_name="Show Deleted",
            info="Whether to include deleted calendar list entries in the result.",
            show=False,
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-show_hidden",
            display_name="Show Hidden",
            info="Whether to show hidden entries.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS-sync_token",
            display_name="Sync Token",
            info="Token obtained from the nextSyncToken field returned on the last page of results from the previous list request.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-calendar_id",
            display_name="Calendar Id",
            info="Identifier of the Google Calendar. Use 'primary' for the currently logged in user's primary calendar.",  # noqa: E501
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-query",
            display_name="Query",
            info="Search term to find events that match these terms in the event's summary, description, location, attendee's displayName, attendee's email, organizer's displayName, organizer's email, etc if needed.",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_EVENT-max_results",
            display_name="Max Results",
            info="Maximum number of events returned on one result page. The page size can never be larger than 2500 events. The default value is 10.",  # noqa: E501
            show=False,
            value=10,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-order_by",
            display_name="Order By",
            info="The order of the events returned in the result. Acceptable values are 'startTime' and 'updated'.",
            show=False,
        ),
        BoolInput(
            name="GOOGLECALENDAR_FIND_EVENT-show_deleted",
            display_name="Show Deleted",
            info="Whether to include deleted events (with status equals 'cancelled') in the result.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_FIND_EVENT-single_events",
            display_name="Single Events",
            info="Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves.",  # noqa: E501
            show=False,
            value=True,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-timeMax",
            display_name="Timemax",
            info="Upper bound (exclusive) for an event's start time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-timeMin",
            display_name="Timemin",
            info="Lower bound (exclusive) for an event's end time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-updated_min",
            display_name="Updated Min",
            info="Lower bound for an event's last modification time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        StrInput(
            name="GOOGLECALENDAR_FIND_EVENT-event_types",
            display_name="Event Types",
            info="List of event types to return. Possible values are: default, outOfOffice, focusTime, workingLocation.",  # noqa: E501
            show=False,
            value=["default", "outOfOffice", "focusTime", "workingLocation"],
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT-page_token",
            display_name="Page Token",
            info="Token specifying which result page to return. Optional.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DUPLICATE_CALENDAR-summary",
            display_name="Summary/Title",
            info="Title of the calendar to be duplicated.",
            show=False,
            value="",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE-calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE-event_id",
            display_name="Event Id",
            info="ID of the event",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE-attendee_email",
            display_name="Attendee Email",
            info="Email address of the attendee to be removed",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_GET_CALENDAR-calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar that needs to be fetched. Default is 'primary'.",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-description",
            display_name="Description",
            info="Description of the event. Can contain HTML. Optional.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-eventType",
            display_name="Event Type",
            info="Type of the event, immutable post-creation. Currently, only 'default'",
            show=False,
            value="default",
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT-create_meeting_room",
            display_name="Create Meeting Room",
            info="If true, a Google Meet link is created and added to the event.",
            show=False,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT-guestsCanSeeOtherGuests",
            display_name="Guests Can See Other Guests",
            info="Whether attendees other than the organizer can see who the event's attendees are.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT-guestsCanInviteOthers",
            display_name="Guests Can Invite Others",
            info="Whether attendees other than the organizer can invite others to the event.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-location",
            display_name="Location",
            info="Geographic location of the event as free-form text.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-summary",
            display_name="Summary/Title",
            info="Summary (title) of the event.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-transparency",
            display_name="Event Transparency",
            info="'opaque' (busy) or 'transparent' (available).",
            show=False,
            value="opaque",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-visibility",
            display_name="Event Visibility",
            info="Event visibility: 'default', 'public', 'private', or 'confidential'.",
            show=False,
            value="default",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-timezone",
            display_name="Timezone",
            info="IANA timezone name (e.g., 'America/New_York'). Required if datetime is naive. If datetime includes timezone info (Z or offset), this field is optional and defaults to UTC.",  # noqa: E501
            show=False,
        ),
        StrInput(
            name="GOOGLECALENDAR_CREATE_EVENT-recurrence",
            display_name="Recurrence",
            info="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events.",
            show=False,
            is_list=True,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT-guests_can_modify",
            display_name="Guests Can Modify",
            info="If True, guests can modify the event.",
            show=False,
            value=False,
            advanced=True,
        ),
        StrInput(
            name="GOOGLECALENDAR_CREATE_EVENT-attendees",
            display_name="Attendees",
            info="List of attendee emails (strings).",
            show=False,
            is_list=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT-send_updates",
            display_name="Send Updates",
            info="Defaults to True. Whether to send updates to the attendees.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-start_datetime",
            display_name="Start Datetime",
            info="Naive date/time (YYYY-MM-DDTHH:MM:SS) with NO offsets or Z. e.g. '2025-01-16T13:00:00'",
            show=False,
            required=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_CREATE_EVENT-event_duration_hour",
            display_name="Event Duration Hour",
            info="Number of hours (0-24).",
            show=False,
            value=0,
        ),
        IntInput(
            name="GOOGLECALENDAR_CREATE_EVENT-event_duration_minutes",
            display_name="Event Duration Minutes",
            info="Number of minutes (0-59).",
            show=False,
            value=30,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT-calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar. `primary` for interacting with the primary calendar.",
            show=False,
            value="primary",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DELETE_EVENT-calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DELETE_EVENT-event_id",
            display_name="Event Id",
            info="ID of the event to be deleted",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-time_min",
            display_name="Time Min",
            info="The start datetime of the interval for the query. Supports multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-time_max",
            display_name="Time Max",
            info="The end datetime of the interval for the query. Supports multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-timezone",
            display_name="Timezone",
            info="Time zone used in the response. Optional. The default is UTC.",
            show=False,
            value="UTC",
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-group_expansion_max",
            display_name="Group Expansion Max",
            info="Maximal number of calendar identifiers to be provided for a single group. Optional. An error is returned for a group with more members than this value. Maximum value is 100.",  # noqa: E501
            show=False,
            value=100,
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-calendar_expansion_max",
            display_name="Calendar Expansion Max",
            info="Maximal number of calendars for which FreeBusy information is to be provided. Optional. Maximum value is 50.",  # noqa: E501
            show=False,
            value=50,
        ),
        StrInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS-items",
            display_name="Items",
            info="List of calendars ids for which to fetch",
            show=False,
            value=["primary"],
            is_list=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD-calendar_id",
            display_name="Calendar Id",
            info="Calendar identifier. To list calendars to retrieve calendar IDs use relevant tools. To access the primary calendar of the currently logged in user, use the 'primary' keyword.",  # noqa: E501
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD-text",
            display_name="Text",
            info="The text describing the event to be created.",
            show=False,
            value="",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD-send_updates",
            display_name="Send Updates",
            info="Guests who should receive notifications about the creation of the new event. Accepted fields include 'all', 'none', 'externalOnly'",
            show=False,
            value="none",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR-calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar that needs to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR-description",
            display_name="Description",
            info="Description of the calendar. Optional.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR-location",
            display_name="Location",
            info="Geographic location of the calendar as free-form text.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR-summary",
            display_name="Title/Summary",
            info="Title of the calendar. This field is required and cannot be left blank as per the Google Calendar API requirements.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR-timezone",
            display_name="Timezone",
            info="The time zone of the calendar. (Formatted as an IANA Time Zone Database name, e.g. 'Europe/Zurich').",
            show=False,
        ),
        IntInput(
            name="GOOGLECALENDAR_GET_CURRENT_DATE_TIME-timezone",
            display_name="Timezone",
            info="The timezone offset from UTC to retrieve current date and time, like for location of UTC+6, you give 6, for UTC -9, your give -9.",  # noqa: E501
            show=False,
            value=0,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-description",
            display_name="Description",
            info="Description of the event. Can contain HTML. Optional.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-eventType",
            display_name="EventType",
            info="Type of the event, immutable post-creation. Currently, only 'default' and 'workingLocation' can be created.",  # noqa: E501
            show=False,
            value="default",
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-create_meeting_room",
            display_name="Create Meeting Room",
            info="If true, a Google Meet link is created and added to the event.",
            show=False,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-guestsCanSeeOtherGuests",
            display_name="Guests Can See Other Guests",
            info="Whether attendees other than the organizer can see who the event's attendees are.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-guestsCanInviteOthers",
            display_name="Guests Can Invite Others",
            info="Whether attendees other than the organizer can invite others to the event.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-location",
            display_name="Location",
            info="Geographic location of the event as free-form text.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-summary",
            display_name="Summary/Title",
            info="Summary (title) of the event.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-transparency",
            display_name="Event Transparency",
            info="'opaque' (busy) or 'transparent' (available).",
            show=False,
            value="opaque",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-visibility",
            display_name="Event Visibility",
            info="Event visibility: 'default', 'public', 'private', or 'confidential'.",
            show=False,
            value="default",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-timezone",
            display_name="Timezone",
            info="IANA timezone name (e.g., 'America/New_York'). Required if datetime is naive. If datetime includes timezone info (Z or offset), this field is optional and defaults to UTC.",  # noqa: E501
            show=False,
        ),
        StrInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-recurrence",
            display_name="Recurrence",
            info="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events.",
            show=False,
            is_list=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-guests_can_modify",
            display_name="Guests Can Modify",
            info="If True, guests can modify the event.",
            show=False,
            value=False,
            advanced=True,
        ),
        StrInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-attendees",
            display_name="Attendees",
            info="List of attendee emails (strings).",
            show=False,
            is_list=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-send_updates",
            display_name="Send Updates",
            info="Defaults to True. Whether to send updates to the attendees.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-start_datetime",
            display_name="Start Datetime",
            info="Naive date/time (YYYY-MM-DDTHH:MM:SS) with NO offsets or Z. e.g. '2025-01-16T13:00:00'",
            show=False,
            required=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-event_duration_hour",
            display_name="Event Duration Hour",
            info="Number of hours (0-24).",
            show=False,
            value=0,
        ),
        IntInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-event_duration_minutes",
            display_name="Event Duration Minutes",
            info="Number of minutes (0-59).",
            show=False,
            value=30,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT-event_id",
            display_name="Event Id",
            info="ID of the event to be updated",
            show=False,
            required=True,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Response", method="execute_action"),
    ]

    def execute_action(self) -> Message:
        """Execute Google Calendar action and return response as Message."""
        toolset = self._build_wrapper()

        try:
            action_key = self._display_to_enum_map.get(self.action)

            enum_name = getattr(Action, action_key)  # type: ignore[arg-type]
            params = {}
            if action_key in self._actions_data:
                for field in self._actions_data[action_key]["parameters"]:
                    param_name = field.split("-", 1)[1] if "-" in field else field
                    value = getattr(self, field)

                    if value is None or value == "" or value == [] or value == [""] or value == ['']:
                        continue

                    if field in self._bool_variables:
                        value = bool(value)

                    params[param_name] = value

            result = toolset.execute_action(
                action=enum_name,
                params=params,
            )
            self.status = result
            return Message(text=str(result))
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action
            if self.action in self._actions_data:
                display_name = self._actions_data[self.action]["display_name"]
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def show_hide_fields(self, build_config: dict, field_value: Any):
        all_fields = set()
        for action_data in self._actions_data.values():
            all_fields.update(action_data["parameters"])

        for field in all_fields:
            build_config[field]["show"] = False

            if field in self._bool_variables:
                build_config[field]["value"] = False
            elif field in self._list_variables:
                build_config[field]["value"] = []
            else:
                build_config[field]["value"] = ""

        action_key = self._display_to_enum_map.get(field_value)

        if action_key in self._actions_data:
            for field in self._actions_data[action_key]["parameters"]:
                build_config[field]["show"] = True

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        build_config["auth_status"]["show"] = True
        build_config["auth_status"]["advanced"] = False

        if field_name == "tool_mode":
            if field_value:
                build_config["action"]["show"] = False

                all_fields = set()
                for action_data in self._actions_data.values():
                    all_fields.update(action_data["parameters"])
                for field in all_fields:
                    build_config[field]["show"] = False

            else:
                build_config["action"]["show"] = True

        if field_name == "action":
            self.show_hide_fields(build_config, field_value)

        if hasattr(self, "api_key") and self.api_key != "":
            googlecalendar_display_names = list(self._display_to_enum_map.keys())
            build_config["action"]["options"] = googlecalendar_display_names

            try:
                toolset = self._build_wrapper()
                entity = toolset.client.get_entity(id=self.entity_id)

                try:
                    entity.get_connection(app="googlecalendar")
                    build_config["auth_status"]["value"] = "✅"
                    build_config["auth_link"]["show"] = False

                except NoItemsFound:
                    auth_scheme = self._get_auth_scheme("googlecalendar")
                    if auth_scheme.auth_mode == "OAUTH2":
                        build_config["auth_link"]["show"] = True
                        build_config["auth_link"]["advanced"] = False
                        auth_url = self._initiate_default_connection(entity, "googlecalendar")
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

    async def _get_tools(self) -> list[Tool]:
        toolset = self._build_wrapper()
        tools = toolset.get_tools(actions=self._actions_data.keys())
        for tool in tools:
            tool.tags = [tool.name]  # Assigning tags directly
        return tools

    @property
    def enabled_tools(self):
        return [
            "GOOGLECALENDAR_CREATE_EVENT",
            "GOOGLECALENDAR_FIND_EVENT",
        ]
