"""Shared action execution and provider client lifetime."""

from typing import Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action
from lfx.io import DataInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_servicenow.client import ServiceNowClient

__all__ = [
    "Data",
    "DataInput",
    "DropdownInput",
    "IntInput",
    "MessageTextInput",
    "Output",
    "ServiceNowAction",
    "ServiceNowActionComponent",
]


class ServiceNowActionComponent(Component):
    icon = "Server"
    capability_id: ClassVar[str] = ""
    transport: Any = None

    async def call(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
        lease = self.resolve_connection("connection")
        credential = await lease.get_credential()
        async with (
            integration_action(
                self,
                provider="servicenow",
                capability=self.capability_id,
                owner_kind=credential.owner_kind,
            ),
            ServiceNowClient(lease, transport=self.transport) as client,
        ):
            return await client.request(method, path, params=params, body=body)


# Preserve imports of the original helper while component source uses the loader-compatible name.
ServiceNowAction = ServiceNowActionComponent
