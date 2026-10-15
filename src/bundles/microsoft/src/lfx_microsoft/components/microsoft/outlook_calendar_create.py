"""Create a calendar event (POST /me/events)."""

from __future__ import annotations

from typing import Any

from lfx_microsoft.base import (
    BoolInput,
    Data,
    DataInput,
    MessageTextInput,
    MicrosoftGraphComponent,
    MultilineInput,
    Output,
    as_list,
)
from lfx_microsoft.graph import prefer_header
from lfx_microsoft.manifest import connection_input

DEFAULT_TIME_ZONE = "UTC"


class OutlookCalendarCreateComponent(MicrosoftGraphComponent):
    """Create an Outlook calendar event as the connected user."""

    display_name = "Outlook Calendar: Create Event"
    description = "Create a calendar event on the connected user's calendar."
    documentation = "https://learn.microsoft.com/en-us/graph/api/user-post-events"
    name = "OutlookCalendarCreateEvent"
    capability_id = "microsoft.calendar.create"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(name="subject", display_name="Subject", required=True),
        MessageTextInput(
            name="start_time",
            display_name="Start",
            info="ISO 8601 local start, for example 2026-09-01T09:00:00.",
            required=True,
        ),
        MessageTextInput(name="end_time", display_name="End", info="ISO 8601 local end.", required=True),
        MessageTextInput(
            name="time_zone",
            display_name="Time Zone",
            info="dateTimeTimeZone.timeZone for both ends. Defaults to UTC.",
            value=DEFAULT_TIME_ZONE,
        ),
        MultilineInput(name="body", display_name="Body", advanced=True),
        MessageTextInput(name="location", display_name="Location", advanced=True),
        MessageTextInput(
            name="attendees",
            display_name="Attendees",
            info="Required attendee addresses.",
            is_list=True,
            advanced=True,
        ),
        BoolInput(name="is_online_meeting", display_name="Online Meeting", value=False, advanced=True),
        DataInput(
            name="recurrence",
            display_name="Recurrence",
            info="A Graph patternedRecurrence object.",
            advanced=True,
        ),
        MessageTextInput(
            name="calendar_id",
            display_name="Calendar ID",
            info="Defaults to the user's default calendar.",
            advanced=True,
        ),
        MessageTextInput(
            name="transaction_id",
            display_name="Transaction ID",
            info="Client-supplied id that makes a retried create idempotent.",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Event", name="event", method="create_event")]

    def _path(self) -> str:
        calendar = (self.calendar_id or "").strip()
        if calendar:
            return f"/me/calendars/{calendar}/events"
        return "/me/events"

    def _recurrence(self) -> dict[str, Any] | None:
        value = self.recurrence
        if value is None:
            return None
        if isinstance(value, Data):
            return dict(value.data)
        if isinstance(value, dict):
            return value
        return None

    def _event(self) -> dict[str, Any]:
        time_zone = (self.time_zone or "").strip() or DEFAULT_TIME_ZONE
        event: dict[str, Any] = {
            "subject": self.subject,
            "start": {"dateTime": self.start_time, "timeZone": time_zone},
            "end": {"dateTime": self.end_time, "timeZone": time_zone},
        }
        if body := (self.body or ""):
            event["body"] = {"contentType": "text", "content": body}
        if location := (self.location or "").strip():
            event["location"] = {"displayName": location}
        if attendees := as_list(self.attendees):
            event["attendees"] = [{"emailAddress": {"address": address}, "type": "required"} for address in attendees]
        if self.is_online_meeting:
            event["isOnlineMeeting"] = True
        if recurrence := self._recurrence():
            event["recurrence"] = recurrence
        if transaction_id := (self.transaction_id or "").strip():
            event["transactionId"] = transaction_id
        return event

    async def create_event(self) -> Data:
        """Create the event and return the created Graph resource."""
        payload = self._event()
        headers = prefer_header((self.time_zone or "").strip() or DEFAULT_TIME_ZONE)
        lease = self.lease()
        async with self.action(lease) as client:
            response = await client.request(
                "POST",
                self._path(),
                json_body=payload,
                headers=headers or None,
            )
        created = response.json() if response.content else {}
        result = Data(data=created if isinstance(created, dict) else {"response": created})
        self.status = result.data.get("id", "created")
        return result
