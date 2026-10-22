"""Jira snapshot, OAuth and invalid transport contracts."""

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest, IngressSecrets, verify
from langflow.services.triggers.providers.jira import PROVIDER, collector, oauth
from langflow.services.triggers.providers.registry import get_provider
from lfx.integrations.errors import InvalidRequestError, ProviderUnavailableError
from lfx_jira.client import JiraClient
from lfx_jira.schema import SCOPES

from tests.unit.services.triggers.jira_testkit import SITE, issue, lease_for

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(autouse=True)
def configured_site(monkeypatch):
    monkeypatch.setenv("LANGFLOW_JIRA_CLOUD_ID", SITE)


def trigger(kind="jira.issue_updated", state=None):
    return SimpleNamespace(
        kind=kind,
        config={
            "connection": "jira/work",
            "project": "DEMO",
            "delivery_mode": "poll",
            "mechanism_id": "jira.issue.poll",
        },
        provider_state=state or {},
        connection_id=uuid4(),
    )


def patch_client(monkeypatch, handler):
    monkeypatch.setattr(
        collector, "JiraClient", lambda lease: JiraClient(lease, transport=httpx.MockTransport(handler))
    )


async def test_initial_snapshot_has_no_events_and_does_not_mutate_trigger(monkeypatch):
    node = trigger()
    patch_client(monkeypatch, lambda _request: httpx.Response(200, json={"issues": [issue()], "isLast": True}))
    result = await collector.collect(node, lease_for()[0])
    assert result.baseline
    assert not result.items
    assert result.cursor["issues"]["1"]["status"] == "1"
    assert node.provider_state == {}


@pytest.mark.parametrize(
    ("kind", "changed", "expected"),
    [
        ("jira.issue_updated", issue(updated="2026-10-22T11:00:00Z"), 1),
        ("jira.issue_status", issue(updated="2026-10-22T11:00:00Z", status="2"), 1),
        ("jira.issue_status", issue(updated="2026-10-22T11:00:00Z"), 0),
        ("jira.issue_created", issue("2", created="2026-10-22T11:00:00Z"), 1),
        ("jira.issue_created", issue("2", created="2026-10-21T11:00:00Z"), 0),
        ("jira.issue_updated", issue("2"), 0),
    ],
)
async def test_observed_changes_and_old_permission_gains(monkeypatch, kind, changed, expected):
    state = {
        "baseline_complete": True,
        "started_at": "2026-10-22T10:00:00+00:00",
        "issues": {"1": {"updated": "2026-10-22T10:00:00+00:00", "status": "1"}},
    }
    node = trigger(kind, state)
    patch_client(monkeypatch, lambda _request: httpx.Response(200, json={"issues": [changed], "isLast": True}))
    result = await collector.collect(node, lease_for()[0])
    assert len(result.items) == expected
    assert node.provider_state == state
    if expected:
        assert result.items[0]["data"]["project"] == "DEMO"
        assert "synthetic-jira-access" not in str(result.items)
    node.provider_state = result.cursor
    assert not (await collector.collect(node, lease_for()[0])).items


async def test_pagination_is_opaque_bounded_and_atomic(monkeypatch):
    calls = []

    def handler(request):
        import json

        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return httpx.Response(200, json={"issues": [issue()], "nextPageToken": "opaque", "isLast": False})
        assert body["nextPageToken"] == "opaque"
        return httpx.Response(503)

    patch_client(monkeypatch, handler)
    node = trigger()
    with pytest.raises(ProviderUnavailableError):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"issues": [issue(project="OTHER")], "isLast": True},
        {"issues": [issue(), issue()], "isLast": True},
        {"issues": [], "isLast": False},
        {"issues": [], "nextPageToken": "repeat", "isLast": False},
    ],
)
async def test_unrelated_duplicate_and_broken_pages_fail_without_advancing(monkeypatch, payload):
    patch_client(monkeypatch, lambda _request: httpx.Response(200, json=payload))
    node = trigger()
    with pytest.raises(InvalidRequestError):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


@pytest.mark.parametrize(
    "raw",
    [
        {"connection": "other/work", "project": "DEMO"},
        {"connection": "jira/work", "project": 'DEMO" OR 1=1'},
        {"connection": "jira/work", "project": "DEMO", "issue_type_id": "not-numeric"},
        {"connection": "jira/work", "project": "DEMO", "delivery_mode": "push"},
        {"connection": "jira/work", "project": "DEMO", "token": "bad"},
    ],
)
def test_invalid_trigger_targets_and_push_modes_rejected(raw):
    with pytest.raises(
        ValueError, match=r"^(Choose an owned Jira connection|Unsupported Jira trigger|Jira issue sources)"
    ):
        collector.normalize_config("jira.issue_created", raw)


def registration():
    return SimpleNamespace(
        provider="jira",
        profile="user",
        client_type="confidential",
        private_key=None,
        context="self_managed",
        tenant=SITE,
        scopes=list(SCOPES),
        allowed_tenants=[SITE],
    )


async def test_oauth_initial_and_refresh_prove_site_scopes_and_account(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.atlassian.com"
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": SITE, "scopes": list(SCOPES - {"offline_access"})}])
        assert request.url.path == f"/ex/jira/{SITE}/rest/api/3/myself"
        return httpx.Response(200, json={"accountId": "user-1", "active": True})

    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    body = {
        "access_token": "synthetic-jira-access",
        "refresh_token": "synthetic-rotating",
        "expires_in": 3600,
        "scope": "read:jira-work write:jira-work read:jira-user",
    }
    for refresh in [False, True]:
        token, account = await oauth.parse_token(registration(), body, refresh=refresh)
        assert account == {"id": "user-1", "tenant_id": SITE}
        assert "offline_access" in token["scope"]
    assert len(requests) == 4


@pytest.mark.parametrize("failure", ["site", "scopes", "account", "response"])
async def test_oauth_wrong_site_scope_account_and_redirect_fail_closed(monkeypatch, failure):
    def handler(request):
        if failure == "response":
            return httpx.Response(302, headers={"Location": "https://evil.invalid"})
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "other" if failure == "site" else SITE,
                        "scopes": [] if failure == "scopes" else list(SCOPES),
                    }
                ],
            )
        return httpx.Response(200, json={"accountId": "user-1", "active": False})

    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(OAuthError):
        await oauth.parse_token(
            registration(),
            {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expires_in": 3600,
                "scope": " ".join(SCOPES),
            },
            refresh=False,
        )


def test_no_jira_push_verifier_accepts_forged_webhooks(monkeypatch):
    monkeypatch.setattr("langflow.services.triggers.providers.registry.all_providers", lambda: (PROVIDER,))
    with pytest.raises(IngressRejected):
        verify(
            IngressRequest(provider="jira", body=b'{"webhookEvent":"jira:issue_created"}', headers={}, query={}),
            IngressSecrets(),
            tolerance_s=300,
        )
    assert get_provider("jira").verify is None


async def test_oauth_broker_uses_atlassian_json_confidential_exchange(monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from langflow.services.connection.oauth import providers
    from langflow.services.connection.oauth.config import OAuthRegistration
    from langflow.services.triggers.providers import registry

    monkeypatch.setattr(registry, "all_providers", lambda: (PROVIDER,))
    registration = OAuthRegistration(
        provider="jira",
        client_id="operator-app",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/jira/callback",
        tenant=SITE,
        allowed_tenants=[SITE],
        scopes=list(SCOPES),
    )
    params = parse_qs(
        urlsplit(
            providers.authorization_url(registration, state="opaque-state", verifier="verifier", scopes=list(SCOPES))
        ).query
    )
    assert params["audience"] == ["api.atlassian.com"]
    assert params["state"] == ["opaque-state"]
    assert "code_challenge" not in params
    requests = []

    async def exchange(url, data, **kwargs):
        requests.append((url, data, kwargs))
        assert url == "https://auth.atlassian.com/oauth/token"
        assert kwargs == {"json_body": True}
        assert "code_verifier" not in data
        return {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-rotating",
            "expires_in": 3600,
            "scope": " ".join(SCOPES),
        }

    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": SITE, "scopes": list(SCOPES)}])
        return httpx.Response(200, json={"accountId": "user-1", "active": True})

    monkeypatch.setattr(providers, "_request", exchange)
    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    payload, scopes, account = await providers.exchange(
        registration, code="synthetic-code", verifier="verifier", previous_scopes=[]
    )
    assert account["tenant_id"] == SITE
    assert set(scopes) == SCOPES
    assert payload["refresh_token"] == "synthetic-rotating"  # noqa: S105  # pragma: allowlist secret
    await providers.exchange(
        registration,
        refresh_token="previous-refresh",  # noqa: S106  # pragma: allowlist secret
        previous_scopes=list(SCOPES),
    )
    assert requests[1][1]["grant_type"] == "refresh_token"


async def test_continuation_url_is_never_followed_as_a_destination(monkeypatch):
    import json

    calls = []
    malicious = "https://api.atlassian.com/ex/jira/99999999-9999-9999-9999-999999999999/rest/api/3/search/jql"

    def handler(request):
        calls.append(request)
        assert request.url.path == f"/ex/jira/{SITE}/rest/api/3/search/jql"
        if len(calls) == 1:
            return httpx.Response(200, json={"issues": [issue()], "nextPageToken": malicious, "isLast": False})
        assert json.loads(request.content)["nextPageToken"] == malicious
        return httpx.Response(200, json={"issues": [], "isLast": True})

    patch_client(monkeypatch, handler)
    result = await collector.collect(trigger(), lease_for()[0])
    assert result.baseline
    assert len(calls) == 2


async def test_snapshot_limit_fails_without_cursor_mutation(monkeypatch):
    import json

    def handler(request):
        page = int(json.loads(request.content).get("nextPageToken", "0"))
        return httpx.Response(
            200,
            json={
                "issues": [issue(str(page * 100 + index + 1)) for index in range(100)],
                "nextPageToken": str(page + 1),
                "isLast": False,
            },
        )

    patch_client(monkeypatch, handler)
    node = trigger()
    with pytest.raises(InvalidRequestError, match="5000"):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


def test_optional_issue_type_filter_is_numeric_and_query_scoped():
    from lfx_jira.schema import search_body

    config = collector.normalize_config(
        "jira.issue_status", {"connection": "jira/work", "project": "DEMO", "issue_type_id": "10001"}
    )
    assert config["issue_type_id"] == "10001"
    assert (
        search_body("DEMO", issue_type_id="10001")["jql"] == 'project = "DEMO" AND issuetype = "10001" ORDER BY key ASC'
    )
    with pytest.raises(InvalidRequestError):
        search_body("DEMO", issue_type_id='10001" OR 1=1')


async def test_filtered_snapshot_rejects_an_unrelated_issue_type(monkeypatch):
    patch_client(monkeypatch, lambda _request: httpx.Response(200, json={"issues": [issue()], "isLast": True}))
    node = trigger()
    node.config["issue_type_id"] = "10002"
    with pytest.raises(InvalidRequestError, match="outside the selected"):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


@pytest.mark.parametrize("policy", ["all", "read", "write"])
@pytest.mark.parametrize("refresh", [False, True])
async def test_dialog_scope_defaults_authorize_and_exchange_without_overgrant(monkeypatch, policy, refresh):
    import json
    from pathlib import Path
    from urllib.parse import parse_qs, urlsplit

    from langflow.services.connection.oauth import providers
    from langflow.services.connection.oauth.config import OAuthRegistration
    from langflow.services.triggers.providers import registry
    from lfx.integrations.errors import ScopeMissingError
    from lfx_jira.client import JiraClient
    from lfx_jira.schema import READ, USER, WRITE

    from tests.unit.services.triggers.jira_testkit import credential, lease_for

    root = Path(__file__).resolve().parents[6]
    scenarios = json.loads((root / "src/bundles/jira/tests/fixtures/consent-scopes.json").read_text())
    selected_scopes = next(item["scopes"] for item in scenarios if item["policy"] == policy)
    monkeypatch.setattr(registry, "all_providers", lambda: (PROVIDER,))
    selected = OAuthRegistration(
        provider="jira",
        client_id="operator-app",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/jira/callback",
        tenant=SITE,
        allowed_tenants=[SITE],
        scopes=list(SCOPES),
    )
    query = parse_qs(
        urlsplit(
            providers.authorization_url(
                selected,
                state="opaque",
                verifier="verifier",
                scopes=selected_scopes,
            )
        ).query
    )
    assert set(query["scope"][0].split()) == set(selected_scopes)

    async def exchange(*_args, **_kwargs):
        return {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 3600,
            "scope": " ".join(selected_scopes),
        }

    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": SITE, "scopes": selected_scopes}])
        return httpx.Response(200, json={"accountId": "user-1", "active": True})

    monkeypatch.setattr(providers, "_request", exchange)
    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    exchange_args = (
        {"refresh_token": "synthetic-previous"} if refresh else {"code": "synthetic-code", "verifier": "verifier"}
    )
    _, granted, account = await providers.exchange(selected, previous_scopes=selected_scopes, **exchange_args)
    assert set(granted) == set(selected_scopes)
    assert account == {"id": "user-1", "tenant_id": SITE}
    assert {READ, USER} <= set(granted)
    if policy == "read":
        calls = []
        client = JiraClient(
            lease_for(credential(granted_scopes=frozenset(granted)))[0],
            transport=httpx.MockTransport(lambda request: calls.append(request)),
        )
        try:
            with pytest.raises(ScopeMissingError):
                await client.request("PUT", "/rest/api/3/issue/DEMO-1", body={}, scopes=frozenset({WRITE}))
        finally:
            await client.aclose()
        assert calls == []


async def test_site_grant_cannot_borrow_write_scope_from_another_site(monkeypatch):
    from lfx_jira.schema import READ, USER, WRITE

    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(
                200,
                json=[
                    {"id": SITE, "scopes": [READ, USER]},
                    {"id": "other-site", "scopes": [READ, USER, WRITE]},
                ],
            )
        return httpx.Response(200, json={"accountId": "user-1", "active": True})

    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    token, _ = await oauth.parse_token(
        registration(),
        {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 3600,
            "scope": " ".join(SCOPES),
        },
        refresh=False,
    )
    assert set(token["scope"].split()) == {READ, USER, "offline_access"}
