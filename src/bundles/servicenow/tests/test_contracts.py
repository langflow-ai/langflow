"""Contracts exercise actual action components and the bearer transport."""

from dataclasses import replace

import httpx
import pytest
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
)
from lfx.integrations.models import ConnectionAccount, ConnectionRef, ResolvedCredential
from lfx_servicenow.client import ServiceNowClient
from lfx_servicenow.components.servicenow import (
    ServiceNowCreateRecordComponent,
    ServiceNowReadRecordComponent,
    ServiceNowSearchRecordsComponent,
    ServiceNowUpdateRecordComponent,
)
from lfx_servicenow.manifest import manifest
from lfx_servicenow.schema import READ_SCOPE, WRITE_SCOPE, fields, literal, origin, table
from pydantic import SecretStr

ROOT = "https://acme.service-now.com"
ID = "a" * 32
RECORD = {"sys_id": ID, "number": "INC001", "state": "1", "access_token": "never-output"}


class Lease:
    ref = ConnectionRef(provider="servicenow", name="work")

    def __init__(self, **changes):
        self.value = replace(
            ResolvedCredential(
                access_token=SecretStr("test-access"),
                scopes_verified=True,
                granted_scopes=frozenset({READ_SCOPE, WRITE_SCOPE}),
                provider="servicenow",
                identity="user_delegated",
                account=ConnectionAccount(id=ROOT, tenant_id=ROOT),
            ),
            **changes,
        )
        self.refreshes = 0

    async def get_credential(self):
        return self.value

    async def get_token_after_auth_error(self, _error, *, rejected_token):
        assert rejected_token == "test-access"  # noqa: S105 - synthetic credential
        self.refreshes += 1
        self.value = replace(self.value, access_token=SecretStr("refreshed-access"))
        return "refreshed-access"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SERVICENOW_ORIGIN", ROOT)
    monkeypatch.setenv("LANGFLOW_SERVICENOW_TABLES", "incident,problem,change_request")


@pytest.mark.parametrize(
    "value",
    [
        "http://acme.service-now.com",
        "https://acme.service-now.com.evil.test",
        "https://127.0.0.1",
        "https://a:b@acme.service-now.com",
        "https://acme.service-now.com:443",
        "https://acme.service-now.com/path",
    ],
)
def test_operator_origin_rejects_untrusted_hosts(monkeypatch, value):
    monkeypatch.setenv("LANGFLOW_SERVICENOW_ORIGIN", value)
    with pytest.raises(InvalidRequestError):
        origin()


@pytest.mark.parametrize("value", ["x^ORactive=true", "javascript:gs.getUserID()", "x\nfoo", "x=bar", "a%5eb", ""])
def test_filter_literals_cannot_inject_encoded_queries(value):
    with pytest.raises(InvalidRequestError):
        literal(value)


def test_approved_tables_and_fields(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SERVICENOW_TABLES", "incident")
    for value in ["sys_user", "../incident", "problem"]:
        with pytest.raises(InvalidRequestError):
            table(value)
    for value in [
        {"sys_created_on": "yesterday"},
        {"state": {"value": "2"}},
        {"state": "2^ORactive=true"},
        {"assigned_to": "../x"},
    ]:
        with pytest.raises(InvalidRequestError):
            fields(value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("component", "method", "verb", "values"),
    [
        (
            ServiceNowSearchRecordsComponent,
            "search_records",
            "GET",
            {"filter_field": "number", "filter_value": "INC001", "limit": 10},
        ),
        (ServiceNowReadRecordComponent, "read_record", "GET", {"record_id": ID}),
        (ServiceNowCreateRecordComponent, "create_record", "POST", {"fields": {"short_description": "Example"}}),
        (ServiceNowUpdateRecordComponent, "update_record", "PATCH", {"record_id": ID, "fields": {"state": "2"}}),
    ],
)
async def test_actual_components_send_bounded_requests(monkeypatch, component, method, verb, values):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == "acme.service-now.com"
        assert request.headers["Authorization"] == "Bearer test-access"
        result = [RECORD] if method == "search_records" else RECORD
        return httpx.Response(200, json={"result": result})

    node = component()
    node.set(table="incident", **values)
    monkeypatch.setattr(component, "resolve_connection", lambda *_: Lease())
    node.transport = httpx.MockTransport(handler)
    result = await getattr(node, method)()
    data = result[0].data if isinstance(result, list) else result.data
    assert data == {"sys_id": ID, "number": "INC001", "state": "1"}
    assert len(seen) == 1
    assert seen[0].method == verb
    if method == "search_records":
        assert seen[0].url.params["sysparm_query"] == "number=INC001^ORDERBYsys_id"
    if verb in {"POST", "PATCH"}:
        import json

        assert json.loads(seen[0].content) == values["fields"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "github"},
        {"identity": "service"},
        {"account": None},
        {"account": ConnectionAccount(id="wrong", tenant_id="https://other.service-now.com")},
        {"token_type": "Basic"},
        {"scopes_verified": False},
        {"granted_scopes": frozenset()},
    ],
)
async def test_denials_happen_before_network(changes):
    async with ServiceNowClient(
        Lease(**changes), transport=httpx.MockTransport(lambda _: pytest.fail("network call"))
    ) as client:
        with pytest.raises((ConnectionNotAuthorizedError, ScopeMissingError)):
            await client.request("GET", "/api/now/v1/table/incident")


@pytest.mark.asyncio
async def test_reactive_refresh_and_origin_binding():
    lease = Lease()
    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(401 if len(seen) == 1 else 200, json={"result": RECORD})

    async with ServiceNowClient(lease, transport=httpx.MockTransport(handler)) as client:
        await client.request("GET", f"/api/now/v1/table/incident/{ID}")
    assert seen == ["Bearer test-access", "Bearer refreshed-access"]
    assert lease.refreshes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (302, ProviderUnavailableError),
        (401, AuthExpiredError),
        (403, ConnectionNotAuthorizedError),
        (429, RateLimitedError),
        (500, ProviderUnavailableError),
    ],
)
async def test_errors_never_echo_credentials(status, error):
    async with ServiceNowClient(
        Lease(), transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"error": "test-access"}))
    ) as client:
        with pytest.raises(error) as exc:
            await client.request("GET", "/api/now/v1/table/incident")
    assert "test-access" not in str(exc.value)


@pytest.mark.asyncio
async def test_no_ambiguous_write_retry():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        msg = "test-access"
        raise httpx.ReadTimeout(msg, request=request)

    async with ServiceNowClient(Lease(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderUnavailableError) as exc:
            await client.request("POST", "/api/now/v1/table/incident", body={"short_description": "Example"})
    assert count == 1
    assert "test-access" not in str(exc.value)


def test_manifest_matches_connection_inputs():
    declared = manifest()
    assert len(declared.capabilities) == 6
    for component in [
        ServiceNowSearchRecordsComponent,
        ServiceNowReadRecordComponent,
        ServiceNowCreateRecordComponent,
        ServiceNowUpdateRecordComponent,
    ]:
        spec = next(item for item in declared.capabilities if item.id == component.capability_id)
        connection = next(field for field in component.inputs if field.name == "connection")
        assert set(connection.required_scopes) == set(spec.required_scopes)
        assert connection.capabilities == [spec.id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example/api/now/v1/table/incident",
        "/api/now/v1/table/sys_user",
        "/api/now/v1/table/incident/../sys_user",
        "/api/now/v1/table/incident?x=1",
        "/api/now/v1/table/incident/%2f%2fevil",
    ],
)
async def test_client_rejects_unapproved_paths_before_credentials(path):
    class Unresolved:
        async def get_credential(self):
            pytest.fail("Forbidden path resolved credentials")

    async with ServiceNowClient(
        Unresolved(), transport=httpx.MockTransport(lambda _: pytest.fail("network"))
    ) as client:
        with pytest.raises(InvalidRequestError):
            await client.request("GET", path)


@pytest.mark.asyncio
async def test_refreshed_credential_cannot_switch_instances():
    class DriftedLease(Lease):
        async def get_token_after_auth_error(self, error, *, rejected_token):
            result = await super().get_token_after_auth_error(error, rejected_token=rejected_token)
            self.value = replace(
                self.value, account=ConnectionAccount(id="other", tenant_id="https://other.service-now.com")
            )
            return result

    count = 0

    def handler(_request):
        nonlocal count
        count += 1
        return httpx.Response(401, json={"error": "test-access"})

    async with ServiceNowClient(DriftedLease(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", "/api/now/v1/table/incident")
    assert count == 1
