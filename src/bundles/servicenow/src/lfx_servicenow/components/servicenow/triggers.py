"""Declarative ticket sources use the leased server listener."""

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import DropdownInput

from lfx_servicenow.manifest import connection_input
from lfx_servicenow.schema import TABLES


class _ServiceNowSource:
    provider = "servicenow"
    needs_connection = True
    icon = "Server"

    def trigger_config(self) -> dict:
        return {"connection": getattr(self, "connection", None), "table": self.table, "delivery_mode": "poll"}


class ServiceNowOnTicketCreatedTriggerComponent(_ServiceNowSource, BaseTriggerComponent):
    display_name = "ServiceNow On Ticket Created"
    description = "Observe new tickets after enabling. Requires a self-managed listener."
    name = "ServiceNowOnTicketCreatedTrigger"
    trigger_kind = "servicenow.ticket_created"
    inputs = [
        connection_input("servicenow.trigger.ticket_created", required=False),
        DropdownInput(name="table", display_name="Table", options=list(TABLES), value="incident"),
    ]


class ServiceNowOnStatusChangeTriggerComponent(_ServiceNowSource, BaseTriggerComponent):
    display_name = "ServiceNow On Observed Status Change"
    description = "Compare observed ticket states. Intermediate transitions and deletions are not captured."
    name = "ServiceNowOnStatusChangeTrigger"
    trigger_kind = "servicenow.status_changed"
    inputs = [
        connection_input("servicenow.trigger.status_changed", required=False),
        DropdownInput(name="table", display_name="Table", options=list(TABLES), value="incident"),
    ]
