"""Update explicit scalar fields on one record."""

from lfx_salesforce.base import Data, DataInput, DropdownInput, MessageTextInput, Output, SalesforceActionComponent
from lfx_salesforce.manifest import connection_input
from lfx_salesforce.schema import API_ROOT, FIELDS, object_name, record_id, values


class SalesforceUpdateRecordComponent(SalesforceActionComponent):
    display_name = "Salesforce Update Record"
    description = "Update supported fields on one existing Salesforce record."
    name = "SalesforceUpdateRecord"
    capability_id = "salesforce.record.update"
    inputs = [
        connection_input(capability_id),
        DropdownInput(name="object_name", display_name="Object", options=list(FIELDS), value="Account"),
        MessageTextInput(name="record_id", display_name="Record ID", required=True),
        DataInput(name="record_values", display_name="Field Values", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="update_record")]

    async def update_record(self) -> Data:
        obj = object_name(self.object_name)
        identifier = record_id(self.record_id)
        payload = values(obj, self.record_values, create=False)
        await self.perform(
            obj=obj,
            operation="update",
            fields=list(payload),
            path=f"{API_ROOT}/sobjects/{obj}/{identifier}",
            payload=payload,
        )
        output = Data(data={"id": identifier, "success": True})
        self.status = output
        return output
