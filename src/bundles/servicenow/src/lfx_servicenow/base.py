"""Shared action execution and provider client lifetime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action
from lfx.io import DataInput, DropdownInput, IntInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_servicenow.client import ServiceNowClient

if TYPE_CHECKING:
    from lfx.integrations.models import CredentialLease

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
    icon = "ServiceNow"
    capability_id: ClassVar[str] = ""
    transport: Any = None

    async def authorize_connection(self) -> CredentialLease:
        lease = self.resolve_connection("connection")
        await lease.get_credential()
        return lease

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        body: dict | None = None,
        lease: CredentialLease | None = None,
    ) -> dict:
        if lease is None:
            lease = await self.authorize_connection()
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
