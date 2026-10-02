"""Declarative Google Workspace source nodes; server-side adapters own delivery."""

from __future__ import annotations

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, DropdownInput, StrInput

_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _connection(scope: str, capability: str) -> ConnectionRefInput:
    return ConnectionRefInput(
        name="connection",
        display_name="Google Connection",
        provider="google",
        auth_profile_id="user",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=[scope],
        capabilities=[capability],
        required=False,
        info="Choose a connection owned by the flow owner and allow background runs before enabling this source.",
    )


class _GoogleSource:
    provider = "google"
    needs_connection = True
    icon = "Google"

    def trigger_config(self) -> dict:
        return {
            "connection": getattr(self, "connection", None),
            "delivery_mode": getattr(self, "delivery_mode", "auto"),
            "calendar_id": getattr(self, "calendar_id", None),
            "pubsub_topic": getattr(self, "pubsub_topic", None),
            "pubsub_service_account": getattr(self, "pubsub_service_account", None),
        }


class GoogleOnCalendarTriggerComponent(_GoogleSource, BaseTriggerComponent):
    display_name = "Google Calendar: On Event"
    description = "Run when an event on the selected calendar changes."
    name = "GoogleOnCalendarTrigger"
    trigger_kind = "google.calendar"
    inputs = [
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery Mode",
            options=["auto", "push", "poll"],
            value="auto",
            advanced=True,
            info="Auto uses push when a public HTTPS callback is configured. Poll requires a listener process.",
        ),
        _connection(_CALENDAR_SCOPE, "google.trigger.calendar"),
        StrInput(name="calendar_id", display_name="Calendar ID", value="primary", required=False),
    ]
