"""Declarative Microsoft Graph source nodes; server-side adapters own delivery."""

from __future__ import annotations

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, DropdownInput


def _connection(scope: str, capability: str) -> ConnectionRefInput:
    return ConnectionRefInput(
        name="connection",
        display_name="Microsoft Connection",
        provider="microsoft",
        auth_profile_id="user",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=[scope],
        capabilities=[capability],
        required=False,
        info="Choose a connection owned by the flow owner and allow background runs before enabling this source.",
    )


class _MicrosoftSource:
    provider = "microsoft"
    needs_connection = True
    icon = "Microsoft"

    def trigger_config(self) -> dict:
        return {
            "connection": getattr(self, "connection", None),
            "delivery_mode": getattr(self, "delivery_mode", "auto"),
            "site_id": getattr(self, "site_id", None),
        }


class MicrosoftOnCalendarTriggerComponent(_MicrosoftSource, BaseTriggerComponent):
    display_name = "Outlook: On Calendar Event"
    description = "Run when an Outlook calendar event changes."
    name = "MicrosoftOnCalendarTrigger"
    trigger_kind = "microsoft.calendar"
    inputs = [
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery Mode",
            options=["auto", "push", "poll"],
            value="auto",
            advanced=True,
            info="Auto uses push when a public HTTPS callback is configured. Poll requires a listener process.",
        ),
        _connection("Calendars.Read", "microsoft.trigger.calendar"),
    ]
