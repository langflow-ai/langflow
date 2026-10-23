"""Read one Salesforce record through explicit scalar field selection."""

from lfx_salesforce.base import Data, DropdownInput, MessageTextInput, Output, SalesforceActionComponent
from lfx_salesforce.manifest import connection_input
from lfx_salesforce.schema import API_ROOT, FIELDS, invalid, object_name, record_id, selected_fields


class SalesforceReadRecordComponent(SalesforceActionComponent):
    display_name = "Salesforce Read Record"
    description = "Read supported scalar fields from one visible Salesforce record."
    name = "SalesforceReadRecord"
    capability_id = "salesforce.record.read"
    inputs = [
        connection_input(capability_id),
        DropdownInput(name="object_name", display_name="Object", options=list(FIELDS), value="Account"),
        MessageTextInput(name="record_id", display_name="Record ID", required=True),
        MessageTextInput(name="fields", display_name="Fields", info="Comma-separated supported fields."),
    ]
    outputs = [Output(display_name="Record", name="record", method="read_record")]

    async def read_record(self) -> Data:
        obj = object_name(self.object_name)
        identifier = record_id(self.record_id)
        fields = selected_fields(obj, getattr(self, "fields", None))
        result = await self.perform(
            obj=obj,
            operation="read",
            fields=fields,
            path=f"{API_ROOT}/sobjects/{obj}/{identifier}",
            params={"fields": ",".join(fields)},
        )
        if not isinstance(result, dict) or record_id(result.get("Id"))[: len(identifier)] != identifier:
            msg = "Salesforce returned an unrelated record."
            raise invalid(msg)
        output = Data(data={key: value for key, value in result.items() if key in fields})
        self.status = output
        return output
