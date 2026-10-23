"""Create a single record without automatic mutation retries."""

from lfx_salesforce.base import Data, DataInput, DropdownInput, Output, SalesforceActionComponent
from lfx_salesforce.manifest import connection_input
from lfx_salesforce.schema import API_ROOT, FIELDS, invalid, object_name, record_id, values


class SalesforceCreateRecordComponent(SalesforceActionComponent):
    display_name = "Salesforce Create Record"
    description = "Create one record using supported fields and the connected account's permissions."
    name = "SalesforceCreateRecord"
    capability_id = "salesforce.record.create"
    inputs = [
        connection_input(capability_id),
        DropdownInput(name="object_name", display_name="Object", options=list(FIELDS), value="Account"),
        DataInput(name="record_values", display_name="Field Values", required=True),
    ]
    outputs = [Output(display_name="Result", name="result", method="create_record")]

    async def create_record(self) -> Data:
        obj = object_name(self.object_name)
        payload = values(obj, self.record_values, create=True)
        result = await self.perform(
            obj=obj, operation="create", fields=list(payload), path=f"{API_ROOT}/sobjects/{obj}/", payload=payload
        )
        if not isinstance(result, dict) or result.get("success") is not True:
            msg = "Salesforce did not confirm record creation."
            raise invalid(msg)
        output = Data(data={"id": record_id(result.get("id")), "success": True})
        self.status = output
        return output
