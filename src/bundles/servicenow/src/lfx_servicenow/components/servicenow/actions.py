"""Read and change only approved ServiceNow ticket tables and fields."""

from lfx_servicenow.base import (
    Data,
    DataInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    Output,
    ServiceNowActionComponent,
)
from lfx_servicenow.manifest import connection_input
from lfx_servicenow.schema import TABLES, fields, literal, record_id, result_record, table

_MAX_PAGE_SIZE = 100


def _table():
    return DropdownInput(name="table", display_name="Table", options=list(TABLES), value="incident")


class ServiceNowSearchRecordsComponent(ServiceNowActionComponent):
    display_name = "ServiceNow Search Tickets"
    description = "Search one approved ticket table with a single exact filter."
    name = "ServiceNowSearchRecords"
    capability_id = "servicenow.records.search"
    inputs = [
        connection_input(capability_id),
        _table(),
        DropdownInput(
            name="filter_field", display_name="Filter Field", options=["number", "state", "assigned_to"], value="number"
        ),
        MessageTextInput(name="filter_value", display_name="Exact Value", required=True),
        IntInput(name="limit", display_name="Page Size", value=50),
        MessageTextInput(
            name="after_id",
            display_name="After Record ID",
            advanced=True,
            info="Use the last returned sys_id to request the next page.",
        ),
    ]
    outputs = [Output(name="records", display_name="Records", method="search_records")]

    async def search_records(self) -> list[Data]:
        chosen = table(self.table)
        if self.filter_field not in {"number", "state", "assigned_to"}:
            msg = "Choose a supported filter field."
            raise ValueError(msg)
        value = literal(self.filter_value)
        if self.filter_field == "assigned_to":
            record_id(value)
        if not isinstance(self.limit, int) or isinstance(self.limit, bool) or not 1 <= self.limit <= _MAX_PAGE_SIZE:
            msg = "Page Size must be between 1 and 100."
            raise TypeError(msg)
        query = f"{self.filter_field}={value}"
        if self.after_id:
            query += f"^sys_id>{record_id(self.after_id)}"
        body = await self.call(
            "GET",
            f"/api/now/v1/table/{chosen}",
            params={
                "sysparm_query": query + "^ORDERBYsys_id",
                "sysparm_limit": self.limit,
            },
        )
        if not isinstance(body["result"], list):
            msg = "ServiceNow returned an invalid record page."
            raise TypeError(msg)
        rows = [Data(data=result_record(row)) for row in body["result"]]
        self.status = rows
        return rows


class ServiceNowReadRecordComponent(ServiceNowActionComponent):
    display_name = "ServiceNow Read Ticket"
    description = "Read one ticket by its sys_id from an approved table."
    name = "ServiceNowReadRecord"
    capability_id = "servicenow.records.read"
    inputs = [
        connection_input(capability_id),
        _table(),
        MessageTextInput(name="record_id", display_name="Record ID", required=True),
    ]
    outputs = [Output(name="record", display_name="Record", method="read_record")]

    async def read_record(self) -> Data:
        path = f"/api/now/v1/table/{table(self.table)}/{record_id(self.record_id)}"
        result = Data(data=result_record((await self.call("GET", path))["result"]))
        self.status = result
        return result


class ServiceNowCreateRecordComponent(ServiceNowActionComponent):
    display_name = "ServiceNow Create Ticket"
    description = "Create one ticket using approved fields. Automatic write retries are disabled."
    name = "ServiceNowCreateRecord"
    capability_id = "servicenow.records.create"
    inputs = [connection_input(capability_id), _table(), DataInput(name="fields", display_name="Fields", required=True)]
    outputs = [Output(name="record", display_name="Record", method="create_record")]

    async def create_record(self) -> Data:
        path = f"/api/now/v1/table/{table(self.table)}"
        payload = fields(self.fields, create=True)
        result = Data(data=result_record((await self.call("POST", path, body=payload))["result"]))
        self.status = result
        return result


class ServiceNowUpdateRecordComponent(ServiceNowActionComponent):
    display_name = "ServiceNow Update Ticket"
    description = "Patch approved ticket fields. ServiceNow ACLs and business rules still apply."
    name = "ServiceNowUpdateRecord"
    capability_id = "servicenow.records.update"
    inputs = [
        connection_input(capability_id),
        _table(),
        MessageTextInput(name="record_id", display_name="Record ID", required=True),
        DataInput(name="fields", display_name="Fields", required=True),
    ]
    outputs = [Output(name="record", display_name="Record", method="update_record")]

    async def update_record(self) -> Data:
        path = f"/api/now/v1/table/{table(self.table)}/{record_id(self.record_id)}"
        payload = fields(self.fields)
        result = Data(data=result_record((await self.call("PATCH", path, body=payload))["result"]))
        self.status = result
        return result
