"""Shared boundaries for Jira action and trigger components."""

from typing import ClassVar

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.custom.custom_component.component import Component
from lfx.integrations.telemetry import integration_action

from lfx_jira.client import JiraClient
from lfx_jira.schema import READ, WRITE


class JiraActionComponent(Component):
    icon = "Ticket"
    capability_id: ClassVar[str] = ""

    def client(self):
        return JiraClient(self.resolve_connection("connection"))

    async def perform(self, method, path, *, body=None, params=None, write=False):
        client = self.client()
        try:
            credential = await client.lease.get_credential()
            async with integration_action(
                self, provider="jira", capability=self.capability_id, owner_kind=credential.owner_kind
            ):
                return await client.request(
                    method, path, body=body, params=params, scopes=frozenset({READ, WRITE} if write else {READ})
                )
        finally:
            await client.aclose()


class JiraIssueTriggerComponent(BaseTriggerComponent):
    provider = "jira"
    needs_connection = True
    icon = "Ticket"

    def trigger_config(self):
        config = {
            "connection": getattr(self, "connection", None),
            "project": getattr(self, "project", ""),
            "delivery_mode": "poll",
        }
        if getattr(self, "issue_type_id", ""):
            config["issue_type_id"] = self.issue_type_id
        return config
