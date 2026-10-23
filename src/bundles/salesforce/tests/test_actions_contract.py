"""Request contracts and credential boundaries for Salesforce record actions."""

import json

import httpx
import pytest
from conftest import RECORD, credential, lease_for, metadata
from lfx.extension import load_extension, validate_extension
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
)
from lfx.integrations.models import ConnectionAccount
from lfx_salesforce.base import SalesforceAction
from lfx_salesforce.client import SalesforceClient
from lfx_salesforce.components.salesforce import (
    SalesforceCreateRecordComponent,
    SalesforceOnRecordTriggerComponent,
    SalesforceReadRecordComponent,
    SalesforceUpdateRecordComponent,
)
from lfx_salesforce.manifest import load_manifest
from lfx_salesforce.schema import API_ROOT, object_name, origin, selected_fields, values


async def run_component(monkeypatch, cls, handler, **inputs):
    requests = []

    def record(request):
        requests.append(request)
        assert request.url.host == "example.my.salesforce.com"
        return handler(request)

    lease, _ = lease_for()
    monkeypatch.setattr(
        SalesforceAction, "client", lambda _self: SalesforceClient(lease, transport=httpx.MockTransport(record))
    )
    component = cls(connection="salesforce/work", object_name="Account", **inputs)
    method = {
        SalesforceReadRecordComponent: "read_record",
        SalesforceCreateRecordComponent: "create_record",
        SalesforceUpdateRecordComponent: "update_record",
    }[cls]
    return await getattr(component, method)(), requests


async def test_read_has_explicit_fields_and_strips_attributes(monkeypatch):
    def handler(request):
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        assert request.url.params["fields"] == "Id,CreatedDate,LastModifiedDate,SystemModstamp,Name"
        return httpx.Response(
            200,
            json={
                "Id": RECORD,
                "Name": "Example",
                "attributes": {"url": "sensitive"},
                "unexpected_secret": "must-not-escape",  # pragma: allowlist secret
            },
        )

    result, requests = await run_component(
        monkeypatch, SalesforceReadRecordComponent, handler, record_id=RECORD, fields="Name"
    )
    assert result.data == {"Id": RECORD, "Name": "Example"}
    assert len(requests) == 2


async def test_create_posts_one_allowlisted_record(monkeypatch):
    def handler(request):
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        assert request.method == "POST"
        assert json.loads(request.content) == {"Name": "Example"}
        return httpx.Response(201, json={"id": RECORD, "success": True, "errors": []})

    result, requests = await run_component(
        monkeypatch, SalesforceCreateRecordComponent, handler, record_values={"Name": "Example"}
    )
    assert result.data == {"id": RECORD, "success": True}
    assert len(requests) == 2


async def test_update_requires_one_explicit_record(monkeypatch):
    def handler(request):
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        assert request.url.path == f"{API_ROOT}/sobjects/Account/{RECORD}"
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"Phone": None}
        return httpx.Response(204)

    result, _ = await run_component(
        monkeypatch, SalesforceUpdateRecordComponent, handler, record_id=RECORD, record_values={"Phone": None}
    )
    assert result.data["success"]


@pytest.mark.parametrize(
    "bad",
    [
        "https://evil.example",
        "https://example.my.salesforce.com.evil.example",
        "https://user:secret@example.my.salesforce.com",  # pragma: allowlist secret
        "https://example.my.salesforce.com:443",
        "http://example.my.salesforce.com",
        "https://127.0.0.1",
        "https://example.my.salesforce.com/path",
        "https://example.my.salesforce.com?x=1",
    ],
)
def test_operator_origin_rejects_unsafe_targets(monkeypatch, bad):
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", bad)
    with pytest.raises(InvalidRequestError):
        origin()


@pytest.mark.parametrize(
    "payload",
    [
        {"Name": {"nested": True}},
        {"Name": True},
        {"OwnerId": RECORD},
        {"Name": "Example", "attributes": {"url": "https://evil.example"}},
        {"Id": RECORD},
        {"Name": ""},
    ],
)
def test_writes_reject_unsupported_fields_and_shapes(payload):
    with pytest.raises(InvalidRequestError):
        values("Account", payload, create=True)


def test_no_soql_or_relationship_field_inputs():
    for value in ["Account WHERE Name != ''", "Account/describe", "Account__c"]:
        with pytest.raises(InvalidRequestError):
            object_name(value)
    with pytest.raises(InvalidRequestError):
        selected_fields("Account", "Name FROM User")
    with pytest.raises(InvalidRequestError):
        selected_fields("Contact", "Account.Name")


@pytest.mark.parametrize(
    "change",
    [
        {"provider": "slack"},
        {"identity": None},
        {"account": None},
        {"account": ConnectionAccount(id="other", tenant_id="https://other.my.salesforce.com")},
    ],
)
async def test_wrong_credential_fails_before_request(change):
    lease, _ = lease_for(credential(**change))
    requests = []
    client = SalesforceClient(lease, transport=httpx.MockTransport(lambda request: requests.append(request)))
    try:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", API_ROOT + "/limits")
        assert not requests
    finally:
        await client.aclose()


async def test_unverified_scope_fails_before_request():
    lease, _ = lease_for(credential(scopes_verified=False))
    client = SalesforceClient(lease)
    try:
        with pytest.raises(ScopeMissingError):
            await client.request("GET", API_ROOT + "/limits")
    finally:
        await client.aclose()


async def test_auth_refresh_retries_once_and_rechecks_org():
    lease, resolver = lease_for(
        credential(), credential(account=ConnectionAccount(id="other", tenant_id="https://other.my.salesforce.com"))
    )
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(401, json=[{"message": "synthetic-access", "errorCode": "INVALID_SESSION_ID"}])

    client = SalesforceClient(lease, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", API_ROOT + "/limits")
        assert len(requests) == 1
        assert len(resolver.calls) == 2
    finally:
        await client.aclose()


async def test_auth_refresh_uses_new_token_once():
    from pydantic import SecretStr

    lease, resolver = lease_for(credential(), credential(access_token=SecretStr("synthetic-new")))
    tokens = []

    def handler(request):
        tokens.append(request.headers["authorization"])
        return httpx.Response(401 if len(tokens) == 1 else 200, json={"ok": True})

    client = SalesforceClient(lease, transport=httpx.MockTransport(handler))
    try:
        assert await client.request("GET", API_ROOT + "/limits") == {"ok": True}
        assert tokens == ["Bearer synthetic-access", "Bearer synthetic-new"]
        assert len(resolver.calls) == 2
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("status", "body", "error"),
    [
        (302, {}, ProviderUnavailableError),
        (401, {}, AuthExpiredError),
        (403, [{"errorCode": "REQUEST_LIMIT_EXCEEDED"}], RateLimitedError),
        (429, {}, RateLimitedError),
        (503, {}, ProviderUnavailableError),
        (400, {}, InvalidRequestError),
    ],
)
async def test_provider_errors_do_not_leak_response_data(status, body, error):
    lease, _ = lease_for()
    client = SalesforceClient(
        lease,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                status, json=body, headers={"Location": "https://evil.example/synthetic-access"}
            )
        ),
    )
    try:
        with pytest.raises(error) as raised:
            await client.request("GET", API_ROOT + "/limits")
        assert "synthetic-access" not in str(raised.value)
    finally:
        await client.aclose()


async def test_timeout_write_is_not_retried():
    lease, _ = lease_for()
    calls = []

    def handler(request):
        calls.append(request)
        msg = "synthetic-access"
        raise httpx.ReadTimeout(msg, request=request)

    client = SalesforceClient(lease, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IntegrationNetworkError) as raised:
            await client.request("POST", API_ROOT + "/sobjects/Account/", json={"Name": "Example"})
        assert len(calls) == 1
        assert "synthetic-access" not in str(raised.value)
    finally:
        await client.aclose()


async def test_field_permission_is_checked_before_mutation(monkeypatch):
    def handler(_request):
        result = metadata()
        result["fields"][4]["createable"] = False
        return httpx.Response(200, json=result)

    with pytest.raises(InvalidRequestError):
        await run_component(monkeypatch, SalesforceCreateRecordComponent, handler, record_values={"Name": "Example"})


def test_extension_loads_components_and_manifest():
    from pathlib import Path

    import lfx_salesforce

    path = Path(lfx_salesforce.__file__).parent
    assert validate_extension(path).ok
    loaded = load_extension(path, distribution="lfx-salesforce")
    assert loaded.ok, loaded.errors
    assert {item.class_name for item in loaded.components} == {
        "SalesforceReadRecordComponent",
        "SalesforceCreateRecordComponent",
        "SalesforceUpdateRecordComponent",
        "SalesforceOnRecordTriggerComponent",
    }
    assert len(load_manifest().capabilities) == 4
    trigger = SalesforceOnRecordTriggerComponent(connection="salesforce/work", object_name="Account")
    assert trigger.trigger_config()["delivery_mode"] == "poll"


@pytest.mark.parametrize(
    ("returned_id", "accepted"),
    [
        ("001D000000INjVeIAL", True),
        ("001D000000INjVfIAL", False),
        ("001d000000INjVeIAL", False),
        ("001D000000INjVe$AL", False),
    ],
)
async def test_read_matches_15_character_id_without_folding_case(monkeypatch, returned_id, accepted):
    identifier = "001D000000INjVe"

    def handler(request):
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        assert request.url.path == f"{API_ROOT}/sobjects/Account/{identifier}"
        return httpx.Response(200, json={"Id": returned_id, "Name": "Example"})

    if accepted:
        result, _ = await run_component(
            monkeypatch, SalesforceReadRecordComponent, handler, record_id=identifier, fields="Name"
        )
        assert result.data == {"Id": returned_id, "Name": "Example"}
    else:
        with pytest.raises(InvalidRequestError):
            await run_component(
                monkeypatch, SalesforceReadRecordComponent, handler, record_id=identifier, fields="Name"
            )


@pytest.mark.parametrize("partition", ["", "demo.", "develop.", "patch.", "sandbox.", "scratch.", "trailblaze."])
def test_operator_origin_accepts_documented_domain_partitions(monkeypatch, partition):
    target = f"https://example.{partition}my.salesforce.com"
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", target)
    assert origin() == target


@pytest.mark.parametrize(
    "target",
    [
        "https://example.free.my.salesforce.com",
        "https://example.unknown.my.salesforce.com",
        "https://example.scratch.my.salesforce.com.evil.example",
        "https://example.scratch.evil.my.salesforce.com",
        "https://example.scratch.my.salesforce.com/path",
        "https://example.scratch.my.salesforce.com?redirect=https://evil.example",
    ],
)
def test_operator_origin_rejects_unsupported_or_forged_partitions(monkeypatch, target):
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", target)
    with pytest.raises(InvalidRequestError):
        origin()
