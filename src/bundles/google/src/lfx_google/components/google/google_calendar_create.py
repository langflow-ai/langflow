"""Calendar: Create Event — wave-1 action (INT-10, google.calendar.create)."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._workspace_client import workspace_action
from ._workspace_inputs import CALENDAR_EVENTS_SCOPE, google_connection_input

CAPABILITY = "google.calendar.create"

SEND_UPDATES_OPTIONS = ["none", "all", "externalOnly"]
# Calendar accepts conferenceDataVersion 0 (ignore conference data) or 1 (honour it).
MAX_CONFERENCE_DATA_VERSION = 1
# An all-day event is a bare date; anything with a time is an RFC 3339 dateTime.
_DATE_LENGTH = len("2026-01-01")


def _event_time(value: str) -> dict[str, str]:
    """Build an Event time object, accepting either a date or an RFC 3339 stamp."""
    stamp = value.strip()
    if len(stamp) == _DATE_LENGTH and stamp.count("-") == 2:  # noqa: PLR2004 - date has two separators
        return {"date": stamp}
    return {"dateTime": stamp}


def _string_list(raw: object) -> list[str]:
    if raw is None or raw == "":
        return []
    values = raw if isinstance(raw, list) else str(raw).split(",")
    return [item.strip() for item in (str(value) for value in values) if item.strip()]


class GoogleCalendarCreateComponent(Component):
    """Create an event on a calendar the connected user can write to."""

    display_name = "Calendar: Create Event"
    description = "Creates an event on a Google Calendar as the connected account."
    documentation: str = "https://docs.langflow.org/bundles-google"
    icon = "Googlecalendar"
    name = "GoogleCalendarCreateComponent"

    inputs = [
        google_connection_input(required_scopes=[CALENDAR_EVENTS_SCOPE], capabilities=[CAPABILITY]),
        MessageTextInput(
            name="calendar_id",
            display_name="Calendar ID",
            info="Calendar to write to. 'primary' is the connected account's own calendar.",
            value="primary",
        ),
        MessageTextInput(name="summary", display_name="Title", required=True),
        MessageTextInput(
            name="start",
            display_name="Start",
            info="RFC 3339 timestamp, or a bare YYYY-MM-DD date for an all-day event.",
            required=True,
        ),
        MessageTextInput(
            name="end",
            display_name="End",
            info="RFC 3339 timestamp, or a bare YYYY-MM-DD date for an all-day event.",
            required=True,
        ),
        MessageTextInput(name="description", display_name="Description", advanced=True),
        MessageTextInput(name="location", display_name="Location", advanced=True),
        MessageTextInput(
            name="attendees",
            display_name="Attendees",
            info="Email addresses to invite.",
            is_list=True,
            advanced=True,
        ),
        DropdownInput(
            name="send_updates",
            display_name="Send Invitations",
            options=SEND_UPDATES_OPTIONS,
            value="none",
            info="Who receives invitation email for this event.",
            advanced=True,
        ),
        MessageTextInput(
            name="recurrence",
            display_name="Recurrence",
            info="RRULE lines, for example 'RRULE:FREQ=WEEKLY;COUNT=4'.",
            is_list=True,
            advanced=True,
        ),
        IntInput(
            name="conference_data_version",
            display_name="Conference Data Version",
            info="Set to 1 to let the request create conference data.",
            value=0,
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Event", name="event", method="create_event")]

    def _event_body(self) -> dict[str, Any]:
        if not self.summary:
            msg = "summary is required."
            raise ValueError(msg)
        if not self.start or not self.end:
            msg = "start and end are required."
            raise ValueError(msg)
        body: dict[str, Any] = {
            "summary": self.summary,
            "start": _event_time(str(self.start)),
            "end": _event_time(str(self.end)),
        }
        if self.description:
            body["description"] = self.description
        if self.location:
            body["location"] = self.location
        attendees = _string_list(self.attendees)
        if attendees:
            body["attendees"] = [{"email": address} for address in attendees]
        recurrence = _string_list(self.recurrence)
        if recurrence:
            body["recurrence"] = recurrence
        return body

    async def create_event(self) -> Data:
        """Create one event and return the created Events resource."""
        body = self._event_body()
        send_updates = self.send_updates or "none"
        if send_updates not in SEND_UPDATES_OPTIONS:
            msg = f"send_updates must be one of {SEND_UPDATES_OPTIONS}, got {send_updates!r}"
            raise ValueError(msg)
        conference_data_version = int(self.conference_data_version or 0)
        if conference_data_version < 0 or conference_data_version > MAX_CONFERENCE_DATA_VERSION:
            msg = f"conference_data_version must be 0 or {MAX_CONFERENCE_DATA_VERSION}"
            raise ValueError(msg)
        params: dict[str, Any] = {
            "calendarId": self.calendar_id or "primary",
            "body": body,
            "sendUpdates": send_updates,
            "conferenceDataVersion": conference_data_version,
        }

        async with workspace_action(self, capability=CAPABILITY, api="calendar", version="v3") as service:
            response = await service.execute(lambda client: client.events().insert(**params))

        data = Data(data=dict(response))
        self.status = data
        return data
