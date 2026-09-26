"""Declarative Microsoft Graph source nodes; server-side adapters own delivery."""

from __future__ import annotations

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, StrInput


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
            "site_id": getattr(self, "site_id", None),
        }


class MicrosoftOnMailTriggerComponent(_MicrosoftSource, BaseTriggerComponent):
    display_name = "Outlook: On Message"
    description = "Run when a message in the owner's Inbox changes."
    name = "MicrosoftOnMailTrigger"
    trigger_kind = "microsoft.mail"
    inputs = [_connection("Mail.Read", "microsoft.trigger.mail")]


class MicrosoftOnCalendarTriggerComponent(_MicrosoftSource, BaseTriggerComponent):
    display_name = "Outlook: On Calendar Event"
    description = "Run when an Outlook calendar event changes."
    name = "MicrosoftOnCalendarTrigger"
    trigger_kind = "microsoft.calendar"
    inputs = [_connection("Calendars.Read", "microsoft.trigger.calendar")]


class MicrosoftOnFileTriggerComponent(_MicrosoftSource, BaseTriggerComponent):
    display_name = "OneDrive or SharePoint: On File"
    description = "Run when a file in the owner's drive or the specified SharePoint site changes."
    name = "MicrosoftOnFileTrigger"
    trigger_kind = "microsoft.file"
    inputs = [
        _connection("Files.Read", "microsoft.trigger.file"),
        StrInput(
            name="site_id",
            display_name="SharePoint Site ID",
            value="",
            required=False,
            info="Leave empty for OneDrive. A SharePoint site also requires Files.Read.All and Sites.Read.All.",
        ),
    ]
