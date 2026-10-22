"""Standalone installed manifest, action and transport contracts."""

import importlib.abc
import json
import sys
from pathlib import Path

import httpx
import pytest
from conftest import SITE, credential, lease_for, page
from lfx.extension import load_extension, validate_extension
from lfx.integrations.errors import (
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationNetworkError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ResourceNotFoundError,
    ScopeMissingError,
)
from lfx.integrations.models import ConnectionAccount
from lfx_confluence.base import ConfluenceActionComponent
from lfx_confluence.client import ConfluenceClient
from lfx_confluence.components.confluence_integrations import (
    ConfluenceCreatePageComponent,
    ConfluenceOnPageCreatedTriggerComponent,
    ConfluenceReadPageComponent,
    ConfluenceSearchPagesComponent,
    ConfluenceUpdatePageComponent,
)
from lfx_confluence.manifest import load_manifest
from lfx_confluence.schema import approved_space, cloud_id, next_cursor, numeric_id


async def run(monkeypatch, cls, method, handler, **inputs):
    lease, _ = lease_for()
    requests = []

    def record(request):
        requests.append(request)
        assert request.url.host == "api.atlassian.com"
        assert request.url.path.startswith(f"/ex/confluence/{SITE}/wiki/api/v2/pages")
        return handler(request)

    monkeypatch.setattr(
        ConfluenceActionComponent,
        "client",
        lambda _self: ConfluenceClient(lease, transport=httpx.MockTransport(record)),
    )
    return (await getattr(cls(connection="confluence/work", **inputs), method)()).data, requests


async def test_read_page_retains_only_explicit_fields(monkeypatch):
    def handler(request):
        assert request.url.params["body-format"] == "storage"
        return httpx.Response(200, json=page())

    data, calls = await run(monkeypatch, ConfluenceReadPageComponent, "read_page", handler, space_id="10", page_id="1")
    assert data["body_storage"] == "<p>Example</p>"
    assert "unexpected_secret" not in str(data)
    assert "synthetic-confluence-access" not in str(data)
    assert len(calls) == 1


async def test_search_exact_title_in_approved_space_with_cursor(monkeypatch):
    title = 'Exact " title'

    def handler(request):
        assert dict(request.url.params) == {
            "space-id": "10",
            "status": "current",
            "sort": "id",
            "subtype": "page",
            "limit": "100",
            "title": title,
            "cursor": "opaque",
        }
        return httpx.Response(
            200, json={"results": [page(title=title)], "_links": {"next": "/wiki/api/v2/pages?cursor=next"}}
        )

    data, _ = await run(
        monkeypatch,
        ConfluenceSearchPagesComponent,
        "search_pages",
        handler,
        space_id="10",
        title=title,
        cursor="opaque",
    )
    assert data["next_cursor"] == "next"


async def test_create_checks_parent_space_and_storage_payload(monkeypatch):
    def handler(request):
        if request.method == "GET":
            assert request.url.path.endswith("/1")
            return httpx.Response(200, json=page())
        assert json.loads(request.content) == {
            "spaceId": "10",
            "status": "current",
            "title": "New",
            "parentId": "1",
            "body": {"representation": "storage", "value": "<p>New</p>"},
        }
        return httpx.Response(201, json=page("2", title="New"))

    data, calls = await run(
        monkeypatch,
        ConfluenceCreatePageComponent,
        "create_page",
        handler,
        space_id="10",
        title="New",
        parent_id="1",
        body_storage="<p>New</p>",
    )
    assert data["id"] == "2"
    assert len(calls) == 2


async def test_update_requires_expected_version_and_increments_once(monkeypatch):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=page(version=4))
        body = json.loads(request.content)
        assert body == {
            "id": "1",
            "status": "current",
            "title": "Changed",
            "body": {"representation": "storage", "value": ""},
            "version": {"number": 5},
        }
        return httpx.Response(200, json=page(version=5))

    data, calls = await run(
        monkeypatch,
        ConfluenceUpdatePageComponent,
        "update_page",
        handler,
        space_id="10",
        page_id="1",
        expected_version=4,
        title="Changed",
        body_storage="",
    )
    assert data["version"] == 5
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["version", "space", "target"])
async def test_update_mismatch_sends_no_write(monkeypatch, failure):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(
            200,
            json=page(
                "2" if failure == "target" else "1",
                version=3 if failure == "version" else 4,
                space="20" if failure == "space" else "10",
            ),
        )

    with pytest.raises(InvalidRequestError):
        await run(
            monkeypatch,
            ConfluenceUpdatePageComponent,
            "update_page",
            handler,
            space_id="10",
            page_id="1",
            expected_version=4,
            title="Changed",
            body_storage="body",
        )


async def test_conflict_does_not_retry_write(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.method)
        return (
            httpx.Response(200, json=page())
            if request.method == "GET"
            else httpx.Response(409, json={"message": "synthetic-confluence-access"})
        )

    with pytest.raises(InvalidRequestError) as caught:
        await run(
            monkeypatch,
            ConfluenceUpdatePageComponent,
            "update_page",
            handler,
            space_id="10",
            page_id="1",
            expected_version=1,
            title="Changed",
            body_storage="body",
        )
    assert calls == ["GET", "PUT"]
    assert "synthetic-confluence-access" not in str(caught.value)


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.invalid/",
        "//evil.invalid",
        "/wiki/api/v2/pages/../1",
        "/wiki/api/v2/pages/1?space=20",
        "/wiki/api/v2/pages/1%2f",
        f"/ex/confluence/{SITE}/wiki/api/v2/pages",
        "/wiki/api/v2/pages/1/attachments",
    ],
)
async def test_arbitrary_targets_cannot_receive_credentials(path):
    client = ConfluenceClient(
        lease_for()[0], transport=httpx.MockTransport(lambda _r: pytest.fail("Unexpected request"))
    )
    try:
        with pytest.raises(InvalidRequestError):
            await client.request("GET", path)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "jira"},
        {"identity": "bot"},
        {"account": ConnectionAccount(id="user", tenant_id="other")},
        {"account": None},
        {"scopes_verified": False},
        {"granted_scopes": frozenset()},
    ],
)
async def test_credential_tenant_identity_and_scopes_fail_closed(changes):
    client = ConfluenceClient(
        lease_for(credential(**changes))[0], transport=httpx.MockTransport(lambda _r: pytest.fail("Unexpected request"))
    )
    try:
        with pytest.raises((ConnectionNotAuthorizedError, ScopeMissingError)):
            await client.request("GET", "/wiki/api/v2/pages")
    finally:
        await client.aclose()


async def test_expired_access_token_refreshes_once_and_revalidates_tenant():
    lease, resolver = lease_for(credential(), credential(access_token=__import__("pydantic").SecretStr("replacement")))
    calls = []

    def handler(request):
        calls.append(request.headers["Authorization"])
        return httpx.Response(401) if len(calls) == 1 else httpx.Response(200, json={"results": []})

    client = ConfluenceClient(lease, transport=httpx.MockTransport(handler))
    try:
        assert await client.request("GET", "/wiki/api/v2/pages") == {"results": []}
        assert calls == ["Bearer synthetic-confluence-access", "Bearer replacement"]
        assert len(resolver.calls) == 2
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthExpiredError),
        (403, ConnectionNotAuthorizedError),
        (404, ResourceNotFoundError),
        (429, RateLimitedError),
        (503, ProviderUnavailableError),
        (302, ProviderUnavailableError),
    ],
)
async def test_provider_errors_never_echo_tokens_or_provider_response(status, error):
    client = ConfluenceClient(
        lease_for()[0],
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(
                status,
                text="synthetic-confluence-access",
                headers={"Retry-After": "inf", "Location": "https://evil.invalid/"},
            )
        ),
    )
    try:
        with pytest.raises(error) as caught:
            await client.request("GET", "/wiki/api/v2/pages")
        assert "synthetic-confluence-access" not in str(caught.value)
    finally:
        await client.aclose()


async def test_network_errors_are_redacted():
    def handler(request):
        message = "synthetic-confluence-access"
        raise httpx.ConnectError(message, request=request)

    client = ConfluenceClient(lease_for()[0], transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IntegrationNetworkError) as caught:
            await client.request("GET", "/wiki/api/v2/pages")
        assert "synthetic-confluence-access" not in str(caught.value)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.invalid/wiki/api/v2/pages?cursor=x",
        "https://api.atlassian.com/ex/confluence/99999999-9999-9999-9999-999999999999/wiki/api/v2/pages?cursor=x",
        "/wiki/api/v2/pages/1?cursor=x",
        "/wiki/api/v2/pages?cursor=x&cursor=y",
        "/wiki/api/v2/pages?other=x",
    ],
)
def test_unsafe_pagination_links_rejected(link):
    with pytest.raises(InvalidRequestError):
        next_cursor({"_links": {"next": link}})


@pytest.mark.parametrize("value", ["", "0", "../1", "10,20", "1?x=2", "https://evil.invalid", 10])
def test_invalid_page_and_space_ids(value):
    with pytest.raises(InvalidRequestError):
        numeric_id(value)


def test_operator_scope_and_canonical_site_are_required(monkeypatch):
    assert approved_space("10") == "10"
    with pytest.raises(InvalidRequestError):
        approved_space("30")
    monkeypatch.setenv("LANGFLOW_CONFLUENCE_SPACE_IDS", "10,garbage")
    with pytest.raises(InvalidRequestError):
        approved_space("10")
    monkeypatch.setenv("LANGFLOW_CONFLUENCE_CLOUD_ID", "https://evil.invalid")
    with pytest.raises(InvalidRequestError):
        cloud_id()


def test_manifest_and_standalone_extension_discovery_do_not_import_backend():
    class BlockBackend(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002
            if fullname == "langflow" or fullname.startswith("langflow."):
                msg = "A standalone bundle imported the backend."
                raise AssertionError(msg)

    blocker = BlockBackend()
    sys.meta_path.insert(0, blocker)
    try:
        path = Path(__file__).parents[1] / "src/lfx_confluence"
        validation = validate_extension(path)
        assert validation.ok
        loaded = load_extension(path)
        assert loaded.ok
        assert len(loaded.components) == 6
        assert {component.bundle for component in loaded.components} == {"confluence_integrations"}
        assert len(load_manifest().capabilities) == 6
        component = ConfluenceOnPageCreatedTriggerComponent(connection="confluence/work", space_id="10")
        assert component.trigger_config()["space_id"] == "10"
    finally:
        sys.meta_path.remove(blocker)


async def test_auth_refresh_cannot_rebind_another_tenant():
    lease, _ = lease_for(credential(), credential(account=ConnectionAccount(id="user-1", tenant_id="other")))
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401)

    client = ConfluenceClient(lease, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", "/wiki/api/v2/pages")
        assert len(calls) == 1
    finally:
        await client.aclose()


async def test_oversized_and_malformed_responses_are_rejected(monkeypatch):
    import lfx_confluence.client as module

    monkeypatch.setattr(module, "MAX_RESPONSE_BYTES", 32)
    for content in ["x" * 33, "not-json"]:
        client = ConfluenceClient(
            lease_for()[0], transport=httpx.MockTransport(lambda _r, value=content: httpx.Response(200, text=value))
        )
        try:
            with pytest.raises(ProviderUnavailableError):
                await client.request("GET", "/wiki/api/v2/pages")
        finally:
            await client.aclose()
