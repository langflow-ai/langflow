"""Exercise record actions through their generated agent tools."""

import json
from types import SimpleNamespace

import httpx
import pytest
from conftest import ORG, RECORD, Resolver, credential, metadata
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_salesforce.base import SalesforceActionComponent
from lfx_salesforce.components.salesforce import (
    SalesforceCreateRecordComponent,
    SalesforceOnRecordTriggerComponent,
    SalesforceReadRecordComponent,
    SalesforceUpdateRecordComponent,
)
from lfx_salesforce.schema import API_ROOT, FIELDS
from pydantic import ValidationError

SECOND_RECORD = "001000000000002AAA"


def _component(monkeypatch, cls, handler):
    resolver = Resolver([credential()])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    monkeypatch.setattr(SalesforceActionComponent, "salesforce_transport", httpx.MockTransport(handler))
    principal = ExecutionPrincipal(kind="actor", user_id="owner", interactive=True)
    vertex = SimpleNamespace(
        outputs=[], graph=SimpleNamespace(execution_principal=principal, flow_id="salesforce-flow")
    )
    component = cls(connection="salesforce/work", _vertex=vertex, _tracing_service=None)
    return component, resolver, principal


@pytest.mark.parametrize(
    ("cls", "required"),
    [
        (SalesforceReadRecordComponent, {"record_id"}),
        (SalesforceCreateRecordComponent, {"record_values"}),
        (SalesforceUpdateRecordComponent, {"record_id", "record_values"}),
    ],
)
async def test_record_tools_expose_arguments_without_connections(cls, required):
    tools = await cls().to_toolkit()

    assert len(tools) == 1
    schema = tools[0].args_schema.model_json_schema()
    assert set(schema["required"]) == required
    assert set(schema["properties"]["object_name"]["enum"]) == set(FIELDS)
    assert "connection" not in schema["properties"]
    if "record_values" in schema["properties"]:
        assert schema["properties"]["record_values"]["type"] == "object"


@pytest.mark.parametrize(
    ("cls", "method", "first", "second"),
    [
        (
            SalesforceReadRecordComponent,
            "GET",
            {"record_id": RECORD, "fields": "Name"},
            {"record_id": SECOND_RECORD, "fields": "Phone"},
        ),
        (
            SalesforceCreateRecordComponent,
            "POST",
            {"record_values": {"Name": "First account"}},
            {"record_values": {"Name": "Second account"}},
        ),
        (
            SalesforceUpdateRecordComponent,
            "PATCH",
            {"record_id": RECORD, "record_values": {"Phone": "111"}},
            {"record_id": SECOND_RECORD, "record_values": {"Phone": None}},
        ),
    ],
)
async def test_record_tool_calls_keep_the_connection_and_use_current_arguments(monkeypatch, cls, method, first, second):
    requests = []

    def handler(request):
        requests.append(request)
        assert str(request.url).startswith(ORG + API_ROOT)
        assert request.headers["authorization"] == "Bearer synthetic-access"
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        if request.method == "GET":
            return httpx.Response(
                200, json={"Id": request.url.path.rsplit("/", 1)[-1], "Name": "Example", "Phone": "111"}
            )
        if request.method == "POST":
            return httpx.Response(201, json={"id": RECORD, "success": True})
        return httpx.Response(204)

    component, resolver, principal = _component(monkeypatch, cls, handler)
    tool = (await component.to_toolkit())[0]

    for values in (first, second):
        result = await tool.ainvoke({"object_name": "Account", **values})
        if method == "GET":
            assert result["Id"] == values["record_id"]
            assert set(result) == {"Id", values["fields"]}
        else:
            assert result["success"] is True

    action_requests = [request for request in requests if not request.url.path.endswith("describe")]
    assert len(requests) == 4
    assert len(action_requests) == 2
    assert all(request.method == method for request in action_requests)
    for request, values in zip(action_requests, (first, second), strict=True):
        if "record_id" in values:
            assert request.url.path == f"{API_ROOT}/sobjects/Account/{values['record_id']}"
        if method == "GET":
            assert values["fields"] in request.url.params["fields"].split(",")
        else:
            assert json.loads(request.content) == values["record_values"]
    assert len(resolver.calls) == 2
    assert all(request.ref.to_handle() == "salesforce/work" for request in resolver.calls)
    assert all(request.principal == principal for request in resolver.calls)
    assert all(request.flow_id == "salesforce-flow" for request in resolver.calls)


async def test_record_tools_reject_unsupported_objects_and_fields_before_resolving(monkeypatch):
    requests = []
    component, resolver, _ = _component(monkeypatch, SalesforceCreateRecordComponent, requests.append)
    tool = (await component.to_toolkit())[0]

    with pytest.raises(ValidationError):
        await tool.ainvoke({"object_name": "User", "record_values": {"Name": "Example"}})
    result = await tool.ainvoke({"object_name": "Account", "record_values": {"Name": "Example", "OwnerId": RECORD}})

    assert "unsupported" in result
    assert not resolver.calls
    assert not requests


def test_record_trigger_does_not_expose_tool_arguments():
    assert not any(getattr(field, "tool_mode", False) for field in SalesforceOnRecordTriggerComponent.inputs)
