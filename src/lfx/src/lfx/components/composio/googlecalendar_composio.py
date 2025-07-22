from typing import Any

from composio import Action

from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.inputs import (
    BoolInput,
    IntInput,
    MessageTextInput,
)
from lfx.logging import logger


class ComposioGoogleCalendarAPIComponent(ComposioBaseComponent):
    """Google Calendar API component for interacting with Google Calendar services."""

    display_name: str = "Google Calendar"
    description: str = "Google Calendar API"
    icon = "Googlecalendar"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlecalendar"

    _actions_data: dict = {
        "GOOGLECALENDAR_UPDATE_EVENT": {
            "display_name": "Update Google Event",
            "action_fields": [
                "GOOGLECALENDAR_UPDATE_EVENT_description",
                "GOOGLECALENDAR_UPDATE_EVENT_eventType",
                "GOOGLECALENDAR_UPDATE_EVENT_create_meeting_room",
                "GOOGLECALENDAR_UPDATE_EVENT_guestsCanSeeOtherGuests",
                "GOOGLECALENDAR_UPDATE_EVENT_guestsCanInviteOthers",
                "GOOGLECALENDAR_UPDATE_EVENT_location",
                "GOOGLECALENDAR_UPDATE_EVENT_summary",
                "GOOGLECALENDAR_UPDATE_EVENT_transparency",
                "GOOGLECALENDAR_UPDATE_EVENT_visibility",
                "GOOGLECALENDAR_UPDATE_EVENT_timezone",
                "GOOGLECALENDAR_UPDATE_EVENT_recurrence",
                "GOOGLECALENDAR_UPDATE_EVENT_guests_can_modify",
                "GOOGLECALENDAR_UPDATE_EVENT_attendees",
                "GOOGLECALENDAR_UPDATE_EVENT_send_updates",
                "GOOGLECALENDAR_UPDATE_EVENT_start_datetime",
                "GOOGLECALENDAR_UPDATE_EVENT_event_duration_hour",
                "GOOGLECALENDAR_UPDATE_EVENT_event_duration_minutes",
                "GOOGLECALENDAR_UPDATE_EVENT_calendar_id",
                "GOOGLECALENDAR_UPDATE_EVENT_event_id",
            ],
        },
        "GOOGLECALENDAR_REMOVE_ATTENDEE": {
            "display_name": "Remove Attendee From Event",
            "action_fields": [
                "GOOGLECALENDAR_REMOVE_ATTENDEE_calendar_id",
                "GOOGLECALENDAR_REMOVE_ATTENDEE_event_id",
                "GOOGLECALENDAR_REMOVE_ATTENDEE_attendee_email",
            ],
        },
        "GOOGLECALENDAR_GET_CURRENT_DATE_TIME": {
            "display_name": "Get Current Date And Time",
            "action_fields": ["GOOGLECALENDAR_GET_CURRENT_DATE_TIME_timezone"],
        },
        "GOOGLECALENDAR_QUICK_ADD": {
            "display_name": "Quick Add Event",
            "action_fields": [
                "GOOGLECALENDAR_QUICK_ADD_calendar_id",
                "GOOGLECALENDAR_QUICK_ADD_text",
                "GOOGLECALENDAR_QUICK_ADD_send_updates",
            ],
        },
        "GOOGLECALENDAR_LIST_CALENDARS": {
            "display_name": "List Google Calendars",
            "action_fields": [
                "GOOGLECALENDAR_LIST_CALENDARS_max_results",
                "GOOGLECALENDAR_LIST_CALENDARS_min_access_role",
                "GOOGLECALENDAR_LIST_CALENDARS_page_token",
                "GOOGLECALENDAR_LIST_CALENDARS_show_deleted",
                "GOOGLECALENDAR_LIST_CALENDARS_show_hidden",
                "GOOGLECALENDAR_LIST_CALENDARS_sync_token",
            ],
        },
        "GOOGLECALENDAR_FIND_EVENT": {
            "display_name": "Find Event",
            "action_fields": [
                "GOOGLECALENDAR_FIND_EVENT_calendar_id",
                "GOOGLECALENDAR_FIND_EVENT_query",
                "GOOGLECALENDAR_FIND_EVENT_max_results",
                "GOOGLECALENDAR_FIND_EVENT_order_by",
                "GOOGLECALENDAR_FIND_EVENT_show_deleted",
                "GOOGLECALENDAR_FIND_EVENT_single_events",
                "GOOGLECALENDAR_FIND_EVENT_timeMax",
                "GOOGLECALENDAR_FIND_EVENT_timeMin",
                "GOOGLECALENDAR_FIND_EVENT_updated_min",
                "GOOGLECALENDAR_FIND_EVENT_event_types",
                "GOOGLECALENDAR_FIND_EVENT_page_token",
            ],
        },
        "GOOGLECALENDAR_CREATE_EVENT": {
            "display_name": "Create Event",
            "action_fields": [
                "GOOGLECALENDAR_CREATE_EVENT_description",
                "GOOGLECALENDAR_CREATE_EVENT_eventType",
                "GOOGLECALENDAR_CREATE_EVENT_create_meeting_room",
                "GOOGLECALENDAR_CREATE_EVENT_guestsCanSeeOtherGuests",
                "GOOGLECALENDAR_CREATE_EVENT_guestsCanInviteOthers",
                "GOOGLECALENDAR_CREATE_EVENT_location",
                "GOOGLECALENDAR_CREATE_EVENT_summary",
                "GOOGLECALENDAR_CREATE_EVENT_transparency",
                "GOOGLECALENDAR_CREATE_EVENT_visibility",
                "GOOGLECALENDAR_CREATE_EVENT_timezone",
                "GOOGLECALENDAR_CREATE_EVENT_recurrence",
                "GOOGLECALENDAR_CREATE_EVENT_guests_can_modify",
                "GOOGLECALENDAR_CREATE_EVENT_attendees",
                "GOOGLECALENDAR_CREATE_EVENT_send_updates",
                "GOOGLECALENDAR_CREATE_EVENT_start_datetime",
                "GOOGLECALENDAR_CREATE_EVENT_event_duration_hour",
                "GOOGLECALENDAR_CREATE_EVENT_event_duration_minutes",
                "GOOGLECALENDAR_CREATE_EVENT_calendar_id",
            ],
        },
        "GOOGLECALENDAR_FIND_FREE_SLOTS": {
            "display_name": "Find Free Slots",
            "action_fields": [
                "GOOGLECALENDAR_FIND_FREE_SLOTS_time_min",
                "GOOGLECALENDAR_FIND_FREE_SLOTS_time_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS_timezone",
                "GOOGLECALENDAR_FIND_FREE_SLOTS_group_expansion_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS_calendar_expansion_max",
                "GOOGLECALENDAR_FIND_FREE_SLOTS_items",
            ],
        },
        "GOOGLECALENDAR_PATCH_CALENDAR": {
            "display_name": "Patch Calendar",
            "action_fields": [
                "GOOGLECALENDAR_PATCH_CALENDAR_calendar_id",
                "GOOGLECALENDAR_PATCH_CALENDAR_description",
                "GOOGLECALENDAR_PATCH_CALENDAR_location",
                "GOOGLECALENDAR_PATCH_CALENDAR_summary",
                "GOOGLECALENDAR_PATCH_CALENDAR_timezone",
            ],
        },
        "GOOGLECALENDAR_GET_CALENDAR": {
            "display_name": "Fetch Google Calendar",
            "action_fields": ["GOOGLECALENDAR_GET_CALENDAR_calendar_id"],
        },
        "GOOGLECALENDAR_DELETE_EVENT": {
            "display_name": "Delete Event",
            "action_fields": ["GOOGLECALENDAR_DELETE_EVENT_calendar_id", "GOOGLECALENDAR_DELETE_EVENT_event_id"],
        },
        "GOOGLECALENDAR_DUPLICATE_CALENDAR": {
            "display_name": "Duplicate Calendar",
            "action_fields": ["GOOGLECALENDAR_DUPLICATE_CALENDAR_summary"],
        },
    }

    _list_variables = {
        "GOOGLECALENDAR_FIND_EVENT_event_types",
        "GOOGLECALENDAR_CREATE_EVENT_recurrence",
        "GOOGLECALENDAR_CREATE_EVENT_attendees",
        "GOOGLECALENDAR_FIND_FREE_SLOTS_items",
        "GOOGLECALENDAR_UPDATE_EVENT_recurrence",
        "GOOGLECALENDAR_UPDATE_EVENT_attendees",
    }

    _all_fields = {field for action_data in _actions_data.values() for field in action_data["action_fields"]}
    _bool_variables = {
        "GOOGLECALENDAR_LIST_CALENDARS_show_deleted",
        "GOOGLECALENDAR_LIST_CALENDARS_show_hidden",
        "GOOGLECALENDAR_FIND_EVENT_show_deleted",
        "GOOGLECALENDAR_FIND_EVENT_single_events",
        "GOOGLECALENDAR_CREATE_EVENT_create_meeting_room",
        "GOOGLECALENDAR_CREATE_EVENT_guestsCanSeeOtherGuests",
        "GOOGLECALENDAR_CREATE_EVENT_guestsCanInviteOthers",
        "GOOGLECALENDAR_CREATE_EVENT_guests_can_modify",
        "GOOGLECALENDAR_CREATE_EVENT_send_updates",
        "GOOGLECALENDAR_UPDATE_EVENT_create_meeting_room",
        "GOOGLECALENDAR_UPDATE_EVENT_guestsCanSeeOtherGuests",
        "GOOGLECALENDAR_UPDATE_EVENT_guestsCanInviteOthers",
        "GOOGLECALENDAR_UPDATE_EVENT_guests_can_modify",
        "GOOGLECALENDAR_UPDATE_EVENT_send_updates",
    }

    inputs = [
        *ComposioBaseComponent.get_base_inputs(),
        IntInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_max_results",
            display_name="Max Results",
            info="Maximum number of entries returned on one result page. The page size can never be larger than 250 entries.",  # noqa: E501
            show=False,
            value=10,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_min_access_role",
            display_name="Min Access Role",
            info="The minimum access role for the user in the returned entries. Accepted values are 'owner' & 'reader'",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_page_token",
            display_name="Page Token",
            info="Token specifying which result page to return.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_show_deleted",
            display_name="Show Deleted",
            info="Whether to include deleted calendar list entries in the result.",
            show=False,
            value=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_show_hidden",
            display_name="Show Hidden",
            info="Whether to show hidden entries.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_LIST_CALENDARS_sync_token",
            display_name="Sync Token",
            info="Token obtained from the nextSyncToken field returned on the last page of results from the previous list request.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_calendar_id",
            display_name="Calendar Id",
            info="Identifier of the Google Calendar. Use 'primary' for the currently logged in user's primary calendar.",  # noqa: E501
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_query",
            display_name="Query",
            info="Search term to find events that match these terms in the event's summary, description, location, attendee's displayName, attendee's email, organizer's displayName, organizer's email, etc if needed.",  # noqa: E501
            show=False,
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_EVENT_max_results",
            display_name="Max Results",
            info="Maximum number of events returned on one result page. The page size can never be larger than 2500 events. The default value is 10.",  # noqa: E501
            show=False,
            value=10,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_order_by",
            display_name="Order By",
            info="The order of the events returned in the result. Acceptable values are 'startTime' and 'updated'.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_FIND_EVENT_show_deleted",
            display_name="Show Deleted",
            info="Whether to include deleted events (with status equals 'cancelled') in the result.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_FIND_EVENT_single_events",
            display_name="Single Events",
            info="Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves.",  # noqa: E501
            show=False,
            value=True,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_timeMax",
            display_name="Timemax",
            info="Upper bound (exclusive) for an event's start time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_timeMin",
            display_name="Timemin",
            info="Lower bound (exclusive) for an event's end time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_updated_min",
            display_name="Updated Min",
            info="Lower bound for an event's last modification time to filter by. Accepts multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_event_types",
            display_name="Event Types",
            info="List of event types to return. Possible values are: default, outOfOffice, focusTime, workingLocation.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_EVENT_page_token",
            display_name="Page Token",
            info="Token specifying which result page to return. Optional.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DUPLICATE_CALENDAR_summary",
            display_name="Summary/Title",
            info="Title of the calendar to be duplicated.",
            show=False,
            value="",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE_calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE_event_id",
            display_name="Event Id",
            info="ID of the event",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_REMOVE_ATTENDEE_attendee_email",
            display_name="Attendee Email",
            info="Email address of the attendee to be removed",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_GET_CALENDAR_calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar that needs to be fetched. Default is 'primary'.",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_description",
            display_name="Description",
            info="Description of the event. Can contain HTML. Optional.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_eventType",
            display_name="Event Type",
            info="Type of the event, immutable post-creation. Currently, only 'default'",
            show=False,
            value="default",
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT_create_meeting_room",
            display_name="Create Meeting Room",
            info="If true, a Google Meet link is created and added to the event.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT_guestsCanSeeOtherGuests",
            display_name="Guests Can See Other Guests",
            info="Whether attendees other than the organizer can see who the event's attendees are.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT_guestsCanInviteOthers",
            display_name="Guests Can Invite Others",
            info="Whether attendees other than the organizer can invite others to the event.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_location",
            display_name="Location",
            info="Geographic location of the event as free-form text.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_summary",
            display_name="Summary/Title",
            info="Summary (title) of the event.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_transparency",
            display_name="Event Transparency",
            info="'opaque' (busy) or 'transparent' (available).",
            show=False,
            value="opaque",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_visibility",
            display_name="Event Visibility",
            info="Event visibility: 'default', 'public', 'private', or 'confidential'.",
            show=False,
            value="default",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_timezone",
            display_name="Timezone",
            info="IANA timezone name (e.g., 'America/New_York'). Required if datetime is naive. If datetime includes timezone info (Z or offset), this field is optional and defaults to UTC.",  # noqa: E501
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_recurrence",
            display_name="Recurrence",
            info="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT_guests_can_modify",
            display_name="Guests Can Modify",
            info="If True, guests can modify the event.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_attendees",
            display_name="Attendees",
            info="List of attendee emails (strings).",
            show=False,
        ),
        BoolInput(
            name="GOOGLECALENDAR_CREATE_EVENT_send_updates",
            display_name="Send Updates",
            info="Defaults to True. Whether to send updates to the attendees.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_start_datetime",
            display_name="Start Datetime",
            info="Naive date/time (YYYY-MM-DDTHH:MM:SS) with NO offsets or Z. e.g. '2025-01-16T13:00:00'",
            show=False,
            required=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_CREATE_EVENT_event_duration_hour",
            display_name="Event Duration Hour",
            info="Number of hours (0-24).",
            show=False,
            value=0,
            advanced=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_CREATE_EVENT_event_duration_minutes",
            display_name="Event Duration Minutes",
            info="Number of minutes (0-59).",
            show=False,
            value=30,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_CREATE_EVENT_calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar. `primary` for interacting with the primary calendar.",
            show=False,
            value="primary",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DELETE_EVENT_calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_DELETE_EVENT_event_id",
            display_name="Event Id",
            info="ID of the event to be deleted",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_time_min",
            display_name="Time Min",
            info="The start datetime of the interval for the query. Supports multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_time_max",
            display_name="Time Max",
            info="The end datetime of the interval for the query. Supports multiple formats:, 1. ISO format with timezone (e.g., 2024-12-06T13:00:00Z), 2. Comma-separated format (e.g., 2024,12,06,13,00,00), 3. Simple datetime format (e.g., 2024-12-06 13:00:00)",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_timezone",
            display_name="Timezone",
            info="Time zone used in the response. Optional. The default is UTC.",
            show=False,
            value="UTC",
            advanced=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_group_expansion_max",
            display_name="Group Expansion Max",
            info="Maximal number of calendar identifiers to be provided for a single group. Optional. An error is returned for a group with more members than this value. Maximum value is 100.",  # noqa: E501
            show=False,
            value=100,
            advanced=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_calendar_expansion_max",
            display_name="Calendar Expansion Max",
            info="Maximal number of calendars for which FreeBusy information is to be provided. Optional. Maximum value is 50.",  # noqa: E501
            show=False,
            value=50,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_FIND_FREE_SLOTS_items",
            display_name="Items",
            info="List of calendars ids for which to fetch",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD_calendar_id",
            display_name="Calendar Id",
            info="Calendar identifier. To list calendars to retrieve calendar IDs use relevant tools. To access the primary calendar of the currently logged in user, use the 'primary' keyword.",  # noqa: E501
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD_text",
            display_name="Text",
            info="The text describing the event to be created.",
            show=False,
            value="",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_QUICK_ADD_send_updates",
            display_name="Send Updates",
            info="Guests who should receive notifications about the creation of the new event. Accepted fields include 'all', 'none', 'externalOnly'",  # noqa: E501
            show=False,
            value="none",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR_calendar_id",
            display_name="Calendar Id",
            info="The ID of the Google Calendar that needs to be updated.",
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR_description",
            display_name="Description",
            info="Description of the calendar. Optional.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR_location",
            display_name="Location",
            info="Geographic location of the calendar as free-form text.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR_summary",
            display_name="Title/Summary",
            info="Title of the calendar. This field is required and cannot be left blank as per the Google Calendar API requirements.",  # noqa: E501
            show=False,
            required=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_PATCH_CALENDAR_timezone",
            display_name="Timezone",
            info="The time zone of the calendar. (Formatted as an IANA Time Zone Database name, e.g. 'Europe/Zurich').",
            show=False,
            advanced=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_GET_CURRENT_DATE_TIME_timezone",
            display_name="Timezone",
            info="The timezone offset from UTC to retrieve current date and time, like for location of UTC+6, you give 6, for UTC -9, your give -9.",  # noqa: E501
            show=False,
            value=0,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_description",
            display_name="Description",
            info="Description of the event. Can contain HTML. Optional.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_eventType",
            display_name="EventType",
            info="Type of the event, immutable post-creation. Currently, only 'default' and 'workingLocation' can be created.",  # noqa: E501
            show=False,
            value="default",
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_create_meeting_room",
            display_name="Create Meeting Room",
            info="If true, a Google Meet link is created and added to the event.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_guestsCanSeeOtherGuests",
            display_name="Guests Can See Other Guests",
            info="Whether attendees other than the organizer can see who the event's attendees are.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_guestsCanInviteOthers",
            display_name="Guests Can Invite Others",
            info="Whether attendees other than the organizer can invite others to the event.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_location",
            display_name="Location",
            info="Geographic location of the event as free-form text.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_summary",
            display_name="Summary/Title",
            info="Summary (title) of the event.",
            show=False,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_transparency",
            display_name="Event Transparency",
            info="'opaque' (busy) or 'transparent' (available).",
            show=False,
            value="opaque",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_visibility",
            display_name="Event Visibility",
            info="Event visibility: 'default', 'public', 'private', or 'confidential'.",
            show=False,
            value="default",
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_timezone",
            display_name="Timezone",
            info="IANA timezone name (e.g., 'America/New_York'). Required if datetime is naive. If datetime includes timezone info (Z or offset), this field is optional and defaults to UTC.",  # noqa: E501
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_recurrence",
            display_name="Recurrence",
            info="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events.",
            show=False,
            advanced=True,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_guests_can_modify",
            display_name="Guests Can Modify",
            info="If True, guests can modify the event.",
            show=False,
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_attendees",
            display_name="Attendees",
            info="List of attendee emails (strings).",
            show=False,
        ),
        BoolInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_send_updates",
            display_name="Send Updates",
            info="Defaults to True. Whether to send updates to the attendees.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_start_datetime",
            display_name="Start Datetime",
            info="Naive date/time (YYYY-MM-DDTHH:MM:SS) with NO offsets or Z. e.g. '2025-01-16T13:00:00'",
            show=False,
            required=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_event_duration_hour",
            display_name="Event Duration Hour",
            info="Number of hours (0-24).",
            show=False,
            value=0,
            advanced=True,
        ),
        IntInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_event_duration_minutes",
            display_name="Event Duration Minutes",
            info="Number of minutes (0-59).",
            show=False,
            value=30,
            advanced=True,
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_calendar_id",
            display_name="Calendar Id",
            info="ID of the Google Calendar",
            show=False,
            value="primary",
        ),
        MessageTextInput(
            name="GOOGLECALENDAR_UPDATE_EVENT_event_id",
            display_name="Event Id",
            info="ID of the event to be updated",
            show=False,
            required=True,
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
                message_str = result.get("error", {})
                return {"error": message_str}

            result_data = result.get("data", [])
            if (
                len(result_data) != 1
                and not self._actions_data.get(action_key, {}).get("result_field")
                and self._actions_data.get(action_key, {}).get("get_result_field")
            ):
                msg = f"Expected a dict with a single key, got {len(result_data)} keys: {result_data.keys()}"
                raise ValueError(msg)
            if action_key == "GOOGLECALENDAR_GET_CURRENT_DATE_TIME":
                return result_data
            return result_data[next(iter(result_data))]
        except Exception as e:
            logger.error(f"Error executing action: {e}")
            display_name = self.action[0]["name"] if isinstance(self.action, list) and self.action else str(self.action)
            msg = f"Failed to execute {display_name}: {e!s}"
            raise ValueError(msg) from e

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        return super().update_build_config(build_config, field_value, field_name)
