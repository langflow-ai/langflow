"""List calendar events in a window (GET /me/calendarView)."""

from __future__ import annotations

from lfx_microsoft.base import (
    Data,
    IntInput,
    Message,
    MessageTextInput,
    MicrosoftGraphComponent,
    Output,
    as_list,
)
from lfx_microsoft.graph import odata_params, prefer_header
from lfx_microsoft.manifest import connection_input

DEFAULT_TOP = 50


class OutlookCalendarListComponent(MicrosoftGraphComponent):
    """List events between two instants, with recurring series expanded."""

    display_name = "Outlook Calendar: List Events"
    description = "List the connected user's calendar events in a time window."
    documentation = "https://learn.microsoft.com/en-us/graph/api/user-list-calendarview"
    name = "OutlookCalendarListEvents"
    capability_id = "microsoft.calendar.list"

    inputs = [
        connection_input(capability_id),
        MessageTextInput(
            name="start_time",
            display_name="Start",
            # ``start`` is a reserved Component method name, so the field is
            # ``start_time``; the Graph query parameter is unchanged.
            info="ISO 8601 start of the window, for example 2026-09-01T00:00:00.",
            required=True,
        ),
        MessageTextInput(
            name="end_time",
            display_name="End",
            info="ISO 8601 end of the window.",
            required=True,
        ),
        MessageTextInput(
            name="calendar_id",
            display_name="Calendar ID",
            info="Defaults to the user's default calendar.",
            advanced=True,
        ),
        IntInput(name="top", display_name="Max Results", value=DEFAULT_TOP),
        MessageTextInput(
            name="select",
            display_name="Select Fields",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="time_zone",
            display_name="Time Zone",
            info="Windows or IANA time zone for the returned times (Prefer: outlook.timezone).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Events", name="events", method="list_events"),
        Output(display_name="Next Link", name="next_link", method="next_page_link"),
    ]

    _next_link: str | None = None

    def _path(self) -> str:
        calendar = (self.calendar_id or "").strip()
        if calendar:
            return f"/me/calendars/{calendar}/calendarView"
        return "/me/calendarView"

    async def list_events(self) -> list[Data]:
        """Return the expanded event instances as Data rows."""
        params = odata_params(
            top=self.top or DEFAULT_TOP,
            select=as_list(self.select) or None,
            extra={"startDateTime": self.start_time, "endDateTime": self.end_time},
        )
        headers = prefer_header((self.time_zone or "").strip() or None)
        lease = self.lease()
        async with self.action(lease) as client:
            items, next_link = await client.paginate(
                self._path(),
                params=params,
                headers=headers or None,
                limit=self.top or DEFAULT_TOP,
            )
        self._next_link = next_link
        rows = [Data(data=item) for item in items]
        self.status = f"{len(rows)} event(s)"
        return rows

    async def next_page_link(self) -> Message:
        """Return the unfollowed ``@odata.nextLink``, if Graph supplied one."""
        if self._next_link is None:
            await self.list_events()
        return Message(text=self._next_link or "")
