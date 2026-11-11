"""Agent tools use the configured connection and bounded ServiceNow payloads."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.tools import ToolException
from lfx.integrations.models import ConnectionAccount, ResolvedCredential
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.base import BaseConnectionResolverService, ConnectionAccessPolicy
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from lfx_servicenow.base import ServiceNowActionComponent
from lfx_servicenow.components.servicenow import (
    ServiceNowCreateRecordComponent,
    ServiceNowReadRecordComponent,
    ServiceNowSearchRecordsComponent,
    ServiceNowUpdateRecordComponent,
)
from lfx_servicenow.schema import READ_SCOPE, WRITE_SCOPE
from pydantic import SecretStr

ROOT = "https://acme.service-now.com"
RECORD_ID = "a" * 32


class RecordingResolver(BaseConnectionResolverService):
    def __init__(self):
        super().__init__()
        self.requests = []
        self.set_ready()

    async def _get_access_policy(self, _request):
        return ConnectionAccessPolicy(owner_kind="user", connection_owner_id="user-1")

    async def _resolve(self, request, _policy):
        self.requests.append(request)
        return ResolvedCredential(
            access_token=SecretStr("servicenow-tool-test-token"),
            scopes_verified=True,
            granted_scopes=frozenset({READ_SCOPE, WRITE_SCOPE}),
            provider="servicenow",
            identity="user_delegated",
            owner_kind="user",
            account=ConnectionAccount(id=ROOT, tenant_id=ROOT),
        )


@pytest.fixture
def tool_context(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SERVICENOW_ORIGIN", ROOT)
    monkeypatch.setenv("LANGFLOW_SERVICENOW_TABLES", "incident,problem,change_request")
    resolver = RecordingResolver()
    monkeypatch.setitem(get_service_manager().services, ServiceType.CONNECTION_RESOLVER_SERVICE, resolver)
    requests = []

    def handler(request):
        requests.append(request)
        record = {"sys_id": RECORD_ID, "number": "INC001", "state": "1", "access_token": "omit"}
        result = [record] if request.method == "GET" and not request.url.path.endswith(RECORD_ID) else record
        return httpx.Response(200, json={"result": result})

    monkeypatch.setattr(ServiceNowActionComponent, "transport", httpx.MockTransport(handler))
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True),
        flow_id=None,
        run_id=None,
    )
    return SimpleNamespace(vertex=SimpleNamespace(graph=graph, outputs=[]), requests=requests, resolver=resolver)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component_class", "arguments", "parameters", "verb"),
    [
        (
            ServiceNowSearchRecordsComponent,
            {"table": "incident", "filter_field": "number", "filter_value": "INC001", "limit": 5},
            {"table", "filter_field", "filter_value", "limit", "after_id"},
            "GET",
        ),
        (
            ServiceNowReadRecordComponent,
            {"table": "incident", "record_id": RECORD_ID},
            {"table", "record_id"},
            "GET",
        ),
        (
            ServiceNowCreateRecordComponent,
            {"table": "incident", "fields": {"short_description": "Example ticket"}},
            {"table", "fields"},
            "POST",
        ),
        (
            ServiceNowUpdateRecordComponent,
            {"table": "incident", "record_id": RECORD_ID, "fields": {"state": "2"}},
            {"table", "record_id", "fields"},
            "PATCH",
        ),
    ],
)
async def test_action_tools_send_runtime_arguments_using_the_configured_connection(
    tool_context, component_class, arguments, parameters, verb
):
    component = component_class(_vertex=tool_context.vertex, connection="servicenow/work")
    [tool] = await component.to_toolkit()

    assert set(tool.args_schema.model_fields) == parameters
    result = await tool.ainvoke(arguments)

    record = result[0]["data"] if isinstance(result, list) else result
    assert record == {"sys_id": RECORD_ID, "number": "INC001", "state": "1"}
    [request] = tool_context.requests
    assert request.method == verb
    assert request.headers["authorization"] == "Bearer servicenow-tool-test-token"
    assert request.url.host == "acme.service-now.com"
    if component_class is ServiceNowSearchRecordsComponent:
        assert request.url.params["sysparm_query"] == "number=INC001^ORDERBYsys_id"
        assert request.url.params["sysparm_limit"] == "5"
    if verb in {"POST", "PATCH"}:
        assert json.loads(request.content) == arguments["fields"]
    assert {resolution.ref.name for resolution in tool_context.resolver.requests} == {"work"}
    assert {resolution.principal.user_id for resolution in tool_context.resolver.requests} == {"user-1"}


@pytest.mark.asyncio
async def test_create_tool_uses_each_payload_and_keeps_the_writable_field_allowlist(tool_context):
    component = ServiceNowCreateRecordComponent(_vertex=tool_context.vertex, connection="servicenow/work")
    [tool] = await component.to_toolkit()

    for description in ("First ticket", "Second ticket"):
        await tool.ainvoke({"fields": {"short_description": description}})
    assert [json.loads(request.content) for request in tool_context.requests] == [
        {"short_description": "First ticket"},
        {"short_description": "Second ticket"},
    ]

    with pytest.raises(ToolException, match="approved writable fields"):
        await tool.coroutine(fields={"sys_created_on": "yesterday"})
    assert len(tool_context.requests) == 2
