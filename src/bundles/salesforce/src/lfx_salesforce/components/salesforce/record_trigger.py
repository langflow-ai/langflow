"""Declare a server-owned record replication poller."""

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import DropdownInput, MessageTextInput

from lfx_salesforce.manifest import connection_input
from lfx_salesforce.schema import FIELDS


class SalesforceOnRecordTriggerComponent(BaseTriggerComponent):
    display_name = "Salesforce On Record Change"
    description = "Poll added or changed record IDs and deliver their latest visible state."
    name = "SalesforceOnRecordTrigger"
    trigger_kind = "salesforce.record"
    provider = "salesforce"
    needs_connection = True
    icon = "Cloud"
    inputs = [
        connection_input("salesforce.trigger.record", required=False),
        DropdownInput(name="object_name", display_name="Object", options=list(FIELDS), value="Account"),
        MessageTextInput(name="fields", display_name="Fields", info="Comma-separated supported scalar fields."),
    ]

    def trigger_config(self) -> dict:
        return {
            "connection": getattr(self, "connection", None),
            "delivery_mode": "poll",
            "object_name": getattr(self, "object_name", "Account"),
            "fields": getattr(self, "fields", None),
        }
