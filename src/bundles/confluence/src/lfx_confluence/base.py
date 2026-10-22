"""Shared Confluence connection and trigger declarations."""

from typing import ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action

from lfx_confluence.client import ConfluenceClient
from lfx_confluence.schema import READ, WRITE


class ConfluenceActionComponent(Component):
    icon = "BookOpen"
    capability_id: ClassVar[str] = ""

    def client(self):
        return ConfluenceClient(self.resolve_connection("connection"))

    async def perform(self, method, path, *, body=None, params=None, write=False):
        client = self.client()
        try:
            credential = await client.lease.get_credential()
            async with integration_action(
                self, provider="confluence", capability=self.capability_id, owner_kind=credential.owner_kind
            ):
                return await client.request(
                    method, path, body=body, params=params, scopes=frozenset({READ, WRITE} if write else {READ})
                )
        finally:
            await client.aclose()


class ConfluencePageTriggerComponent(BaseTriggerComponent):
    provider = "confluence"
    needs_connection = True
    icon = "BookOpen"

    def trigger_config(self):
        return {
            "connection": getattr(self, "connection", None),
            "space_id": getattr(self, "space_id", ""),
            "delivery_mode": "poll",
        }
