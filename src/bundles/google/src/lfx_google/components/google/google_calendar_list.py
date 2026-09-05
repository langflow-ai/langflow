"""Calendar: List Events — wave-1 action (INT-10, google.calendar.list)."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

from ._workspace_client import workspace_action
from ._workspace_inputs import CALENDAR_EVENTS_READONLY_SCOPE, google_connection_input

CAPABILITY = "google.calendar.list"

DEFAULT_MAX_RESULTS = 250
MAX_RESULTS_CEILING = 2500


class GoogleCalendarListComponent(Component):
    """List events on a calendar the connected user can read."""

    display_name = "Calendar: List Events"
    description = "Lists events from a Google Calendar the connected account can read."
    documentation: str = "https://docs.langflow.org/bundles-google"
    icon = "Googlecalendar"
    name = "GoogleCalendarListComponent"

    inputs = [
        google_connection_input(required_scopes=[CALENDAR_EVENTS_READONLY_SCOPE], capabilities=[CAPABILITY]),
        MessageTextInput(
            name="calendar_id",
            display_name="Calendar ID",
            info="Calendar to read. 'primary' is the connected account's own calendar.",
            value="primary",
        ),
        MessageTextInput(
            name="time_min",
            display_name="Start Time",
            info="RFC 3339 lower bound on an event's end time, for example 2026-01-01T00:00:00Z.",
        ),
        MessageTextInput(
            name="time_max",
            display_name="End Time",
            info="RFC 3339 upper bound on an event's start time.",
        ),
        MessageTextInput(name="query", display_name="Query", info="Free-text search across event fields."),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info=f"Events per page, maximum {MAX_RESULTS_CEILING}.",
            value=DEFAULT_MAX_RESULTS,
            advanced=True,
        ),
        BoolInput(
            name="single_events",
            display_name="Expand Recurring Events",
            info="Return individual occurrences instead of recurring-event masters.",
            value=True,
            advanced=True,
        ),
        DropdownInput(
            name="order_by",
            display_name="Order By",
            options=["startTime", "updated"],
            info="startTime requires expanded recurring events.",
            value="startTime",
            advanced=True,
        ),
        MessageTextInput(
            name="page_token", display_name="Page Token", info="Continue a previous listing.", advanced=True
        ),
    ]

    outputs = [
        Output(display_name="Events", name="events", method="list_events"),
        Output(display_name="Listing", name="listing", method="list_page"),
    ]

    def _request_params(self) -> dict[str, Any]:
        max_results = int(self.max_results) if self.max_results else DEFAULT_MAX_RESULTS
        if max_results < 1 or max_results > MAX_RESULTS_CEILING:
            msg = f"max_results must be between 1 and {MAX_RESULTS_CEILING}, got {max_results}"
            raise ValueError(msg)
        single_events = bool(self.single_events)
        order_by = self.order_by or "startTime"
        if order_by == "startTime" and not single_events:
            msg = "Ordering by startTime requires 'Expand Recurring Events' to be enabled."
            raise ValueError(msg)
        params: dict[str, Any] = {
            "calendarId": self.calendar_id or "primary",
            "maxResults": max_results,
            "singleEvents": single_events,
            "orderBy": order_by,
        }
        if self.time_min:
            params["timeMin"] = self.time_min
        if self.time_max:
            params["timeMax"] = self.time_max
        if self.query:
            params["q"] = self.query
        if self.page_token:
            params["pageToken"] = self.page_token
        return params

    async def _list(self) -> dict:
        # One page, one call: both outputs describe the same response.
        cached = getattr(self, "_events_response", None)
        if cached is not None:
            return cached
        params = self._request_params()
        async with workspace_action(self, capability=CAPABILITY, api="calendar", version="v3") as service:
            response = await service.execute(lambda client: client.events().list(**params))
        self._events_response = response
        return response

    async def list_page(self) -> Data:
        """Return the whole ``events.list`` page: events plus paging metadata."""
        response = await self._list()
        data = Data(
            data={
                "events": list(response.get("items", [])),
                "next_page_token": response.get("nextPageToken"),
                "next_sync_token": response.get("nextSyncToken"),
                "time_zone": response.get("timeZone"),
            }
        )
        self.status = data
        return data

    async def list_events(self) -> DataFrame:
        """Return one row per event resource."""
        response = await self._list()
        rows = [Data(data=dict(item)) for item in response.get("items", [])]
        frame = DataFrame(rows)
        self.status = frame
        return frame
