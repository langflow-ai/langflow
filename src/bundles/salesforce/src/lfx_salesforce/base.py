"""Shared component boundary for bounded Salesforce actions."""

from __future__ import annotations

from typing import Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action
from lfx.io import DataInput, DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from lfx_salesforce.client import SalesforceClient

__all__ = [
    "Data",
    "DataInput",
    "DropdownInput",
    "MessageTextInput",
    "Output",
    "SalesforceAction",
    "SalesforceActionComponent",
]


class SalesforceActionComponent(Component):
    icon = "Cloud"
    capability_id: ClassVar[str] = ""
    salesforce_transport: Any = None

    def client(self) -> SalesforceClient:
        return SalesforceClient(self.resolve_connection("connection"), transport=self.salesforce_transport)

    async def perform(
        self,
        *,
        obj: str,
        operation: str,
        fields: list[str],
        path: str,
        params: dict | None = None,
        payload: dict | None = None,
    ) -> Any:
        client = self.client()
        try:
            credential = await client.lease.get_credential()
            async with integration_action(
                self, provider="salesforce", capability=self.capability_id, owner_kind=credential.owner_kind
            ):
                await client.describe(obj, operation=operation, fields=fields)
                return await client.request(
                    {"read": "GET", "create": "POST", "update": "PATCH"}[operation], path, params=params, json=payload
                )
        finally:
            await client.aclose()


# Preserve imports of the original helper while component source uses the loader-compatible name.
SalesforceAction = SalesforceActionComponent
