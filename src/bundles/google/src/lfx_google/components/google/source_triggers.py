"""Declarative Google Workspace source nodes; server-side adapters own delivery."""

from __future__ import annotations

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, StrInput

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


class _GoogleSource(BaseTriggerComponent):
    provider = "google"
    needs_connection = True
    icon = "Google"

    def trigger_config(self) -> dict:
        return {
            "connection": getattr(self, "connection", None),
            "calendar_id": getattr(self, "calendar_id", None),
            "pubsub_topic": getattr(self, "pubsub_topic", None),
            "pubsub_service_account": getattr(self, "pubsub_service_account", None),
        }


class GoogleOnCalendarTriggerComponent(_GoogleSource):
    display_name = "Google Calendar: On Event"
    description = "Run when an event on the selected calendar changes."
    name = "GoogleOnCalendarTrigger"
    trigger_kind = "google.calendar"
    inputs = [
        _connection(_CALENDAR_SCOPE, "google.trigger.calendar"),
        StrInput(name="calendar_id", display_name="Calendar ID", value="primary", required=False),
    ]


class GoogleOnDriveTriggerComponent(_GoogleSource):
    display_name = "Google Drive: On File"
    description = "Run when a file visible under drive.file changes."
    name = "GoogleOnDriveTrigger"
    trigger_kind = "google.drive"
    inputs = [_connection(_DRIVE_SCOPE, "google.trigger.drive")]


class GoogleOnGmailTriggerComponent(_GoogleSource):
    display_name = "Gmail: On Message"
    description = "Run on mailbox changes through a customer-owned Gmail watch and Pub/Sub topic."
    name = "GoogleOnGmailTrigger"
    trigger_kind = "google.gmail"
    inputs = [
        _connection(_GMAIL_SCOPE, "google.trigger.gmail"),
        StrInput(
            name="pubsub_topic",
            display_name="Customer Pub/Sub Topic",
            value="",
            required=False,
            info="A topic in the customer's Google Cloud project, authorized for Gmail to publish notifications.",
        ),
        StrInput(
            name="pubsub_service_account",
            display_name="Pub/Sub Push Service Account",
            value="",
            required=False,
            info="The customer service account configured to sign Pub/Sub push requests to this trigger.",
        ),
    ]
