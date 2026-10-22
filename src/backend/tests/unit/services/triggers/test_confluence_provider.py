"""Confluence snapshot, OAuth broker and invalid push contracts."""

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langflow.services.connection.oauth.config import OAuthError
from langflow.services.triggers.ingress.verifiers import IngressRejected, IngressRequest, IngressSecrets, verify
from langflow.services.triggers.providers.confluence import PROVIDER, collector, oauth
from lfx.integrations.errors import InvalidRequestError, ProviderUnavailableError
from lfx_confluence.client import ConfluenceClient
from lfx_confluence.schema import SCOPES

from tests.unit.services.triggers.confluence_testkit import SITE, configured_site, lease_for, page  # noqa: F401

pytestmark = pytest.mark.no_blockbuster


def trigger(kind="confluence.page_updated", state=None):
    return SimpleNamespace(
        kind=kind,
        config={
            "connection": "confluence/work",
            "space_id": "10",
            "delivery_mode": "poll",
            "mechanism_id": "confluence.page.poll",
        },
        provider_state=state or {},
        connection_id=uuid4(),
    )


def patch_client(monkeypatch, handler):
    monkeypatch.setattr(
        collector, "ConfluenceClient", lambda lease: ConfluenceClient(lease, transport=httpx.MockTransport(handler))
    )


async def test_baseline_is_silent_and_does_not_mutate_trigger(monkeypatch):
    patch_client(monkeypatch, lambda _r: httpx.Response(200, json={"results": [page()]}))
    node = trigger()
    result = await collector.collect(node, lease_for()[0])
    assert result.baseline
    assert not result.items
    assert result.cursor["pages"] == {"1": 1}
    assert node.provider_state == {}


@pytest.mark.parametrize(
    ("kind", "observed", "expected"),
    [
        ("confluence.page_updated", page(version=2), 1),
        ("confluence.page_updated", page(), 0),
        ("confluence.page_updated", page("2", version=5), 0),
        ("confluence.page_created", page("2", created="2026-10-22T11:00:00Z"), 1),
        ("confluence.page_created", page("2", created="2026-10-20T11:00:00Z"), 0),
    ],
)
async def test_changes_deduplicate_and_old_moved_pages_are_not_new(monkeypatch, kind, observed, expected):
    state = {"baseline_complete": True, "started_at": "2026-10-22T10:00:00Z", "pages": {"1": 1}}
    node = trigger(kind, state)
    patch_client(monkeypatch, lambda _r: httpx.Response(200, json={"results": [observed]}))
    result = await collector.collect(node, lease_for()[0])
    assert len(result.items) == expected
    assert node.provider_state == state
    if expected:
        assert result.items[0]["session_key"] == f"confluence:{SITE}:{observed['id']}"
    node.provider_state = result.cursor
    assert not (await collector.collect(node, lease_for()[0])).items


async def test_failed_later_page_cannot_advance_cursor(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                200, json={"results": [page()], "_links": {"next": "/wiki/api/v2/pages?space-id=20&cursor=opaque"}}
            )
        assert request.url.params["space-id"] == "10"
        assert request.url.params["cursor"] == "opaque"
        return httpx.Response(503)

    patch_client(monkeypatch, handler)
    node = trigger()
    with pytest.raises(ProviderUnavailableError):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"results": [page(space="20")]},
        {"results": [page(), page()]},
        {"results": [], "_links": {"next": "/wiki/api/v2/pages?cursor=repeat"}},
        {"results": [], "_links": {"next": "https://evil.invalid/wiki/api/v2/pages?cursor=x"}},
    ],
)
async def test_invalid_snapshots_do_not_advance(monkeypatch, payload):
    patch_client(monkeypatch, lambda _r: httpx.Response(200, json=payload))
    node = trigger()
    with pytest.raises(InvalidRequestError):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


async def test_version_regression_does_not_reset_durable_history(monkeypatch):
    patch_client(monkeypatch, lambda _r: httpx.Response(200, json={"results": [page(version=2)]}))
    node = trigger(state={"baseline_complete": True, "started_at": "2026-10-22T10:00:00Z", "pages": {"1": 3}})
    with pytest.raises(InvalidRequestError):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state["pages"]["1"] == 3


async def test_snapshot_bound_and_cursor_retention(monkeypatch):
    monkeypatch.setattr(collector, "MAX_PAGES", 2)
    counter = 0

    def handler(_request):
        nonlocal counter
        counter += 1
        return httpx.Response(
            200, json={"results": [page(str(counter))], "_links": {"next": f"/wiki/api/v2/pages?cursor={counter}"}}
        )

    patch_client(monkeypatch, handler)
    node = trigger()
    with pytest.raises(InvalidRequestError, match="request limit"):
        await collector.collect(node, lease_for()[0])
    assert node.provider_state == {}


@pytest.mark.parametrize(
    "config",
    [
        {"connection": "other/work", "space_id": "10"},
        {"connection": "confluence/work", "space_id": "30"},
        {"connection": "confluence/work", "space_id": "10", "delivery_mode": "push"},
        {"connection": "confluence/work", "space_id": "10", "token": "no"},
    ],
)
def test_invalid_config_and_push_are_rejected(config):
    with pytest.raises((ValueError, InvalidRequestError)):
        collector.normalize_config("confluence.page_created", config)


def registration():
    return SimpleNamespace(
        provider="confluence",
        profile="user",
        client_type="confidential",
        private_key=None,
        context="self_managed",
        tenant=SITE,
        allowed_tenants=[SITE],
        scopes=list(SCOPES),
    )


def grant():
    return {
        "access_token": "synthetic-confluence-access",
        "refresh_token": "synthetic-rotating",
        "expires_in": 3600,
        "scope": " ".join(SCOPES - {"offline_access"}),
    }


@pytest.mark.parametrize("refresh", [False, True])
async def test_oauth_initial_and_rotating_grant_prove_site_and_account(monkeypatch, refresh):
    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": SITE, "scopes": list(SCOPES)}])
        assert request.url.path == f"/ex/confluence/{SITE}/wiki/rest/api/user/current"
        return httpx.Response(200, json={"accountId": "user-1", "type": "known"})

    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    token, account = await oauth.parse_token(registration(), grant(), refresh=refresh)
    assert account == {"id": "user-1", "tenant_id": SITE}
    assert "offline_access" in token["scope"]


@pytest.mark.parametrize("failure", ["site", "scopes", "account", "redirect"])
async def test_oauth_wrong_tenant_scopes_or_anonymous_account_fail_closed(monkeypatch, failure):
    def handler(request):
        if failure == "redirect":
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
        return httpx.Response(200, json={"accountId": "user-1", "type": "anonymous"})

    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(OAuthError):
        await oauth.parse_token(registration(), grant(), refresh=True)


@pytest.mark.parametrize(
    ("field", "value"), [("tenant", "other"), ("client_type", "public"), ("context", "desktop"), ("scopes", [])]
)
def test_registration_is_operator_owned_and_fixed_site(field, value):
    selected = registration()
    setattr(selected, field, value)
    with pytest.raises(OAuthError):
        oauth.validate_registration(selected)


def test_no_unsigned_webhook_is_accepted(monkeypatch):
    monkeypatch.setattr("langflow.services.triggers.providers.registry.all_providers", lambda: (PROVIDER,))
    with pytest.raises(IngressRejected):
        verify(
            IngressRequest(provider="confluence", body=b'{"event":"page_created"}', headers={}, query={}),
            IngressSecrets(),
            tolerance_s=300,
        )
    assert PROVIDER.verify is None


async def test_shared_oauth_broker_uses_json_and_preserves_rotation(monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from langflow.services.connection.oauth import providers
    from langflow.services.connection.oauth.config import OAuthRegistration
    from langflow.services.triggers.providers import registry

    monkeypatch.setattr(registry, "all_providers", lambda: (PROVIDER,))
    selected = OAuthRegistration(
        provider="confluence",
        client_id="operator-app",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/confluence/callback",
        tenant=SITE,
        allowed_tenants=[SITE],
        scopes=list(SCOPES),
    )
    query = parse_qs(
        urlsplit(
            providers.authorization_url(selected, state="opaque-state", verifier="verifier", scopes=list(SCOPES))
        ).query
    )
    assert query["audience"] == ["api.atlassian.com"]
    assert "code_challenge" not in query
    calls = []

    async def exchange(url, data, **kwargs):
        calls.append(data)
        assert url == "https://auth.atlassian.com/oauth/token"
        assert kwargs == {"json_body": True}
        assert "code_verifier" not in data
        return grant()

    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": SITE, "scopes": list(SCOPES)}])
        return httpx.Response(200, json={"accountId": "user-1", "type": "known"})

    monkeypatch.setattr(providers, "_request", exchange)
    monkeypatch.setattr(oauth, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    _, scopes, account = await providers.exchange(
        selected, code="synthetic-code", verifier="verifier", previous_scopes=[]
    )
    assert account["tenant_id"] == SITE
    assert set(scopes) == SCOPES
    await providers.exchange(selected, refresh_token="synthetic-previous", previous_scopes=list(SCOPES))  # noqa: S106
    assert calls[1]["grant_type"] == "refresh_token"


def test_saved_canvas_defaults_select_polling_and_invalid_space_is_a_validation_error(monkeypatch):
    from langflow.services.triggers.providers import registry
    from langflow.services.triggers.source_arming import normalize_source_config

    monkeypatch.setattr(registry, "all_providers", lambda: (PROVIDER,))
    raw = {"connection": "confluence/work", "space_id": "10", "delivery_mode": None}
    assert normalize_source_config("confluence.page_updated", raw)["delivery_mode"] == "poll"
    raw["space_id"] = "not-a-number"
    with pytest.raises(ValueError, match="approved space"):
        normalize_source_config("confluence.page_updated", raw)


@pytest.mark.parametrize(
    "changes",
    [
        {"access_token": "bad\nheader"},
        {"access_token": "a" * 8193},
        {"refresh_token": "r" * 8193},
        {"expires_in": True},
        {"scope": "read:page:confluence"},
    ],
)
async def test_malformed_oauth_tokens_fail_before_api_io(monkeypatch, changes):
    monkeypatch.setattr(oauth, "http_client", lambda: pytest.fail("Unexpected API request"))
    with pytest.raises(OAuthError):
        await oauth.parse_token(registration(), {**grant(), **changes}, refresh=False)


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
    from lfx_confluence.client import ConfluenceClient
    from lfx_confluence.schema import READ, USER, WRITE

    from tests.unit.services.triggers.confluence_testkit import credential, lease_for

    root = Path(__file__).resolve().parents[6]
    scenarios = json.loads((root / "src/bundles/confluence/tests/fixtures/consent-scopes.json").read_text())
    selected_scopes = next(item["scopes"] for item in scenarios if item["policy"] == policy)
    monkeypatch.setattr(registry, "all_providers", lambda: (PROVIDER,))
    selected = OAuthRegistration(
        provider="confluence",
        client_id="operator-app",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/confluence/callback",
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
        return httpx.Response(200, json={"accountId": "user-1", "type": "known"})

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
        client = ConfluenceClient(
            lease_for(credential(granted_scopes=frozenset(granted)))[0],
            transport=httpx.MockTransport(lambda request: calls.append(request)),
        )
        try:
            with pytest.raises(ScopeMissingError):
                await client.request("PUT", "/wiki/api/v2/pages/1", body={}, scopes=frozenset({WRITE}))
        finally:
            await client.aclose()
        assert calls == []


async def test_site_grant_cannot_borrow_write_scope_from_another_site(monkeypatch):
    from lfx_confluence.schema import READ, USER, WRITE

    def handler(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(
                200,
                json=[
                    {"id": SITE, "scopes": [READ, USER]},
                    {"id": "other-site", "scopes": [READ, USER, WRITE]},
                ],
            )
        return httpx.Response(200, json={"accountId": "user-1", "type": "known"})

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
