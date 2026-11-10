"""Declarative Microsoft Graph source nodes; server-side adapters own delivery."""

from __future__ import annotations

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import ConnectionRefInput, DropdownInput, StrInput


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


class MicrosoftOnFileTriggerComponent(_MicrosoftSource, BaseTriggerComponent):
    display_name = "OneDrive or SharePoint: On File"
    description = "Run when a file in the owner's drive or the specified SharePoint site changes."
    name = "MicrosoftOnFileTrigger"
    trigger_kind = "microsoft.file"
    inputs = [
        DropdownInput(
            name="delivery_mode",
            display_name="Delivery Mode",
            options=["auto", "push", "poll"],
            value="auto",
            advanced=True,
            info="Auto uses push when a public HTTPS callback is configured. Poll requires a listener process.",
        ),
        _connection("Files.Read", "microsoft.trigger.file"),
        StrInput(
            name="site_id",
            display_name="SharePoint Site ID",
            value="",
            required=False,
            info="Leave empty for OneDrive. A SharePoint site also requires Files.Read.All and Sites.Read.All.",
        ),
    ]
