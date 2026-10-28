"""Salesforce OAuth and replication contracts through the installed provider seam."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.triggers.providers.salesforce import PROVIDER, collector, oauth
from langflow.services.triggers.source_errors import SourceConfigurationError
from lfx.integrations.errors import InvalidRequestError, ProviderUnavailableError
from lfx_salesforce.client import SalesforceClient
from lfx_salesforce.schema import iso

from tests.unit.services.triggers.salesforce_testkit import ORG, RECORD, lease_for, metadata


@pytest.fixture(autouse=True)
def configured_org(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", ORG)


def identity_profile(**changes):
    return {
        "organization_id": "00D000000000001AAA",
        "user_id": "005000000000001AAA",
        "active": True,
        "asserted_user": True,
        "display_name": "Example Person",
        **changes,
    }


@pytest.fixture(autouse=True)
def identity_transport(monkeypatch):
    monkeypatch.setattr(
        oauth,
        "identity_http_client",
        lambda _root: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=identity_profile()))
        ),
    )


@pytest.fixture
def source_trigger():
    return SimpleNamespace(
        kind="salesforce.record",
        provider="salesforce",
        connection_id=None,
        config={
            "connection": "salesforce/work",
            "object_name": "Account",
            "fields": ["Name"],
            "delivery_mode": "poll",
            "mechanism_id": "salesforce.record.poll",
        },
        provider_state={},
    )


pytestmark = pytest.mark.no_blockbuster


def registration(**changes):
    return SimpleNamespace(
        provider="salesforce",
        profile="user",
        client_type="confidential",
        context="self_managed",
        private_key=None,
        tenant=ORG,
        scopes=["api", "id", "refresh_token"],
        allowed_tenants=[],
        **changes,
    )


def token(**changes):
    return {
        "access_token": "synthetic-access",
        "refresh_token": "synthetic-refresh",
        "token_type": "Bearer",
        "instance_url": ORG,
        "scope": "api id refresh_token",
        "id": "https://login.salesforce.com/id/00D000000000001AAA/005000000000001AAA",
        **changes,
    }


async def test_oauth_initial_and_refresh_bind_exact_org():
    initial, account = await oauth.parse_token(registration(), token(), refresh=False)
    assert account["tenant_id"] == ORG
    assert account["display"] == "Example Person"
    assert initial["refresh_token"] == "synthetic-refresh"  # noqa: S105 - synthetic fixture
    assert "instance_url" not in initial
    refresh, account = await oauth.parse_token(registration(), token(), refresh=True)
    assert account is None
    assert refresh["access_token"] == "synthetic-access"  # noqa: S105 - synthetic fixture


@pytest.mark.parametrize(
    ("profile", "display"),
    [
        (identity_profile(), "Example Person"),
        (identity_profile(display_name="", email="person@example.com"), "person@example.com"),
        (identity_profile(display_name="x" * 256, username="person@example.com"), "person@example.com"),
        (identity_profile(display_name=None), None),
        (identity_profile(organization_id="00D000000000001", user_id="005000000000001"), "Example Person"),
    ],
)
async def test_verified_identity_display_uses_only_the_configured_org(monkeypatch, profile, display):
    def handler(request):
        assert str(request.url) == ORG + "/id/00D000000000001AAA/005000000000001AAA"
        assert request.headers["Authorization"] == "Bearer synthetic-access"
        return httpx.Response(200, json=profile)

    monkeypatch.setattr(
        oauth, "identity_http_client", lambda _root: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    _, account = await oauth.parse_token(registration(), token(), refresh=False)
    assert account["id"] == "00D000000000001AAA/005000000000001AAA"
    assert account.get("display") == display


@pytest.mark.parametrize(
    "changes",
    [{"organization_id": "other"}, {"user_id": "other"}, {"active": False}, {"asserted_user": False}],
)
async def test_identity_cannot_rebind_a_grant(monkeypatch, changes):
    monkeypatch.setattr(
        oauth,
        "identity_http_client",
        lambda _root: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=identity_profile(**changes)))
        ),
    )
    with pytest.raises(OAuthError, match="could not be verified"):
        await oauth.parse_token(registration(), token(), refresh=False)


@pytest.mark.parametrize("status", [302, 403, 503])
async def test_identity_errors_do_not_follow_redirects_or_echo_tokens(monkeypatch, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://evil.invalid"}, text="synthetic-access")

    monkeypatch.setattr(
        oauth,
        "identity_http_client",
        lambda _root: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False),
    )
    with pytest.raises(OAuthError) as caught:
        await oauth.parse_token(registration(), token(), refresh=False)
    assert len(calls) == 1
    assert "synthetic-access" not in str(caught.value)


@pytest.mark.parametrize("body", [b"not-json", b" " * 65537])
async def test_identity_response_is_bounded_json(monkeypatch, body):
    monkeypatch.setattr(
        oauth,
        "identity_http_client",
        lambda _root: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body))
        ),
    )
    with pytest.raises(OAuthError, match="could not be verified"):
        await oauth.parse_token(registration(), token(), refresh=False)


@pytest.mark.parametrize("refresh", [True, False])
@pytest.mark.parametrize(
    "target",
    [
        "https://other.my.salesforce.com",
        "https://example.my.salesforce.com.evil.example",
        "https://user:secret@example.my.salesforce.com",  # pragma: allowlist secret
        "http://example.my.salesforce.com",
    ],
)
async def test_oauth_rejects_instance_drift_without_leaking(refresh, target):
    with pytest.raises(OAuthError) as raised:
        await oauth.parse_token(registration(), token(instance_url=target), refresh=refresh)
    assert "synthetic" not in str(raised.value)
    assert target not in str(raised.value)


@pytest.mark.parametrize(
    "change",
    [
        {"scope": "full"},
        {"refresh_token": ""},
        {"id": "https://evil.example/id/x/y"},
        {"token_type": "Basic"},
        {"instance_url": []},
        {"token_type": {}},
        {"id": 1},
    ],
)
async def test_oauth_rejects_invalid_identity_and_grants(change):
    with pytest.raises(OAuthError):
        await oauth.parse_token(registration(), token(**change), refresh=False)


def test_adapter_rejects_unbound_and_desktop_registrations():
    for key, value in [
        ("tenant", "https://other.my.salesforce.com"),
        ("context", "desktop"),
        ("client_type", "public"),
        ("profile", "bot"),
    ]:
        candidate = registration()
        setattr(candidate, key, value)
        with pytest.raises(OAuthError):
            oauth.validate_registration(candidate)


@pytest.mark.parametrize(
    "extra",
    [
        {"instance_url": "https://evil.example"},
        {"access_token": "synthetic"},
        {"where": "Name != ''"},
        {"delivery_mode": "push"},
        {"object_name": "User"},
    ],
)
def test_canvas_rejects_urls_credentials_soql_and_unsupported_modes(extra):
    with pytest.raises((ValueError, InvalidRequestError)):
        collector.normalize_config("salesforce.record", {"connection": "salesforce/work", **extra})


def attach_transport(monkeypatch, handler):
    requests = []

    def record(request):
        requests.append(request)
        assert request.url.host == "example.my.salesforce.com"
        return handler(request)

    monkeypatch.setattr(
        collector, "SalesforceClient", lambda lease: SalesforceClient(lease, transport=httpx.MockTransport(record))
    )
    return requests


def change_handler(*, ids=None, records=None, covered=None):
    def handler(request):
        if request.url.path.endswith("describe"):
            return httpx.Response(200, json=metadata())
        if request.url.path.endswith("updated/"):
            assert set(request.url.params) == {"start", "end"}
            return httpx.Response(
                200,
                json={
                    "ids": ids if ids is not None else [RECORD],
                    "latestDateCovered": covered or request.url.params["end"],
                },
            )
        assert request.url.path.endswith("composite/sobjects/Account")
        assert request.url.params["ids"] == RECORD
        return httpx.Response(
            200,
            json=records
            if records is not None
            else [
                {
                    "Id": RECORD,
                    "Name": "Example",
                    "SystemModstamp": "2026-10-22T12:00:00.000Z",
                    "attributes": {"type": "Account"},
                    "unexpected_secret": "must-not-escape",  # pragma: allowlist secret
                }
            ],
        )

    return handler


async def test_first_round_baselines_and_uses_latest_date_covered(monkeypatch, source_trigger):
    requests = attach_transport(monkeypatch, change_handler())
    lease, _ = lease_for()
    result = await collector.collect(source_trigger, lease)
    assert result.baseline
    assert result.cursor["baseline_complete"]
    assert len(result.items) == 1
    assert result.items[0]["data"] == {"Id": RECORD, "Name": "Example", "SystemModstamp": "2026-10-22T12:00:00.000Z"}
    assert result.items[0]["id"] == RECORD
    assert len(requests) == 3
    assert "synthetic" not in repr(result)
    assert "must-not-escape" not in repr(result)


async def test_next_round_overlap_and_complete_cursor(monkeypatch, source_trigger):
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    source_trigger.provider_state = {
        "latest_date_covered": iso(now - timedelta(minutes=2, seconds=20)),
        "baseline_complete": True,
    }
    attach_transport(monkeypatch, change_handler())
    lease, _ = lease_for()
    result = await collector.collect(source_trigger, lease)
    assert not result.baseline
    assert result.previous_cursor == source_trigger.provider_state
    assert result.cursor["latest_date_covered"] == iso(now)
    assert result.items[0]["session_key"] == f"salesforce:Account:{RECORD}"


@pytest.mark.parametrize("failure", ["wrong-id", "truncated-batch", "failed-fetch", "invalid-cursor", "too-many"])
async def test_invalid_round_never_mutates_persisted_cursor(monkeypatch, source_trigger, failure):
    before = dict(source_trigger.provider_state)
    handler = change_handler(
        records=[{"Id": "001000000000002AAA"}]
        if failure == "wrong-id"
        else []
        if failure == "truncated-batch"
        else None,
        covered="2099-01-01T00:00:00Z" if failure == "invalid-cursor" else None,
        ids=[RECORD] * 5001 if failure == "too-many" else None,
    )

    def response(request):
        if failure == "failed-fetch" and "/composite/" in request.url.path:
            return httpx.Response(503, json={"error": "synthetic-access"})
        return handler(request)

    attach_transport(monkeypatch, response)
    lease, _ = lease_for()
    expected = SourceConfigurationError if failure == "too-many" else (InvalidRequestError, ProviderUnavailableError)
    with pytest.raises(expected) as caught:
        await collector.collect(source_trigger, lease)
    if failure == "too-many":
        assert "Reduce source volume before retrying" in str(caught.value)
    assert source_trigger.provider_state == before


async def test_retention_gap_fails_closed_without_http(monkeypatch, source_trigger):
    source_trigger.provider_state = {"latest_date_covered": iso(datetime.now(timezone.utc) - timedelta(days=30))}
    attach_transport(monkeypatch, lambda _request: pytest.fail("Expired cursor reached the API"))
    lease, _ = lease_for()
    with pytest.raises(InvalidRequestError, match="expired"):
        await collector.collect(source_trigger, lease)


async def test_gone_or_inaccessible_record_does_not_become_deletion(monkeypatch, source_trigger):
    attach_transport(monkeypatch, change_handler(records=[None]))
    lease, _ = lease_for()
    result = await collector.collect(source_trigger, lease)
    assert result.items == []


def test_provider_exposes_only_bounded_polling():
    assert PROVIDER.provider_id == "salesforce"
    assert PROVIDER.collect is collector.collect
    assert PROVIDER.verify is None
    assert PROVIDER.provision is None
    assert PROVIDER.revoke is None
    assert PROVIDER.kinds[0].poll_mechanism == "salesforce.record.poll"
    assert PROVIDER.kinds[0].push_mechanism is None
