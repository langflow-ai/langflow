"""Actual action components, standalone discovery and transport boundaries."""

import importlib.abc
import json
import sys
from pathlib import Path

import httpx
import pytest
from conftest import SITE, credential, issue, lease_for
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
from lfx_jira.base import JiraActionComponent
from lfx_jira.client import JiraClient
from lfx_jira.components.jira import (
    JiraCreateIssueComponent,
    JiraOnIssueCreatedTriggerComponent,
    JiraReadIssueComponent,
    JiraSearchIssuesComponent,
    JiraTransitionIssueComponent,
    JiraUpdateIssueComponent,
)
from lfx_jira.manifest import load_manifest
from lfx_jira.schema import cloud_id, issue_key, numeric_id, project_key, search_body


async def run(monkeypatch, cls, method, handler, **inputs):
    lease, _ = lease_for()
    calls = []

    def record(request):
        calls.append(request)
        assert request.url.host == "api.atlassian.com"
        assert request.url.path.startswith(f"/ex/jira/{SITE}/rest/api/3/")
        return handler(request)

    monkeypatch.setattr(
        JiraActionComponent, "client", lambda _self: JiraClient(lease, transport=httpx.MockTransport(record))
    )
    result = await getattr(cls(connection="jira/work", **inputs), method)()
    return result.data, calls


async def test_read_issue_explicit_fields_and_safe_output(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/issue/DEMO-1")
        assert request.url.params["fields"] == "summary,status,created,updated,project,issuetype"
        return httpx.Response(200, json=issue())

    result, calls = await run(monkeypatch, JiraReadIssueComponent, "read_issue", handler, issue="DEMO-1")
    assert result["key"] == "DEMO-1"
    assert len(calls) == 1
    assert "synthetic-jira-access" not in str(result)
    assert "unexpected_secret" not in str(result)


async def test_search_uses_enhanced_api_and_structured_jql(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/search/jql")
        assert request.method == "POST"
        assert json.loads(request.content) == {
            "jql": 'project = "DEMO" AND status = "1" ORDER BY key ASC',
            "fields": ["summary", "status", "created", "updated", "project", "issuetype"],
            "maxResults": 100,
            "nextPageToken": "opaque-page",
        }
        return httpx.Response(200, json={"issues": [issue()], "nextPageToken": "next", "isLast": False})

    result, _ = await run(
        monkeypatch,
        JiraSearchIssuesComponent,
        "search_issues",
        handler,
        project="DEMO",
        status_id="1",
        page="opaque-page",
    )
    assert result["next_page_token"] == "next"  # noqa: S105 - opaque pagination token

    assert result["issues"][0]["id"] == "1"


async def test_create_one_issue_with_adf_description(monkeypatch):
    def handler(request):
        assert request.method == "POST"
        assert request.url.path.endswith("/issue")
        body = json.loads(request.content)
        assert body["fields"]["project"] == {"key": "DEMO"}
        assert body["fields"]["issuetype"] == {"id": "10001"}
        assert body["fields"]["description"]["content"][0]["content"][0]["text"] == "Details"
        return httpx.Response(201, json={"id": "1", "key": "DEMO-1", "self": "untrusted"})

    result, calls = await run(
        monkeypatch,
        JiraCreateIssueComponent,
        "create_issue",
        handler,
        project="DEMO",
        issue_type_id="10001",
        summary="Example",
        description_text="Details",
    )
    assert result == {"id": "1", "key": "DEMO-1"}
    assert len(calls) == 1


async def test_update_one_issue(monkeypatch):
    def handler(request):
        assert request.method == "PUT"
        assert request.url.path.endswith("/issue/DEMO-1")
        assert json.loads(request.content) == {"fields": {"summary": "Changed"}}
        return httpx.Response(204)

    result, _ = await run(
        monkeypatch, JiraUpdateIssueComponent, "update_issue", handler, issue="DEMO-1", summary="Changed"
    )
    assert result == {"key": "DEMO-1", "updated": True}


async def test_transition_checks_workflow_before_mutation(monkeypatch):
    def handler(request):
        assert request.url.path.endswith("/issue/DEMO-1/transitions")
        if request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "31"}]})
        assert json.loads(request.content) == {"transition": {"id": "31"}}
        return httpx.Response(204)

    result, calls = await run(
        monkeypatch, JiraTransitionIssueComponent, "transition_issue", handler, issue="DEMO-1", transition_id="31"
    )
    assert result["transitioned"]
    assert len(calls) == 2


async def test_unavailable_transition_does_not_write(monkeypatch):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"transitions": []})

    with pytest.raises(InvalidRequestError):
        await run(
            monkeypatch, JiraTransitionIssueComponent, "transition_issue", handler, issue="DEMO-1", transition_id="31"
        )


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.test/issue",
        "//evil.test",
        "/rest/api/3/issue/../myself",
        "/rest/api/3/issue/DEMO-1?target=evil",
        "/rest/api/3/issue/DEMO-1%2ftransitions",
        "/rest/api/3/issue/DEMO-1/attachments",
    ],
)
async def test_canvas_paths_cannot_receive_credentials(path):
    lease, _ = lease_for()
    client = JiraClient(lease, transport=httpx.MockTransport(lambda _request: pytest.fail("Unexpected request")))
    try:
        with pytest.raises(InvalidRequestError):
            await client.request("GET", path)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "other"},
        {"identity": "service"},
        {"account": None},
        {"account": ConnectionAccount(id="user", tenant_id="another-site")},
        {"granted_scopes": frozenset()},
        {"scopes_verified": False},
    ],
)
async def test_credential_and_scope_denials_precede_request(changes):
    lease, _ = lease_for(credential(**changes))
    client = JiraClient(lease, transport=httpx.MockTransport(lambda _request: pytest.fail("Unexpected request")))
    try:
        with pytest.raises((ConnectionNotAuthorizedError, ScopeMissingError)):
            await client.request("GET", "/rest/api/3/issue/DEMO-1")
    finally:
        await client.aclose()


async def test_rejected_token_refreshes_once_and_rechecks_site():
    lease, resolver = lease_for(
        credential(),
        credential(access_token=credential().access_token, account=ConnectionAccount(id="user", tenant_id="other")),
    )
    client = JiraClient(lease, transport=httpx.MockTransport(lambda _request: httpx.Response(401)))
    try:
        with pytest.raises(ConnectionNotAuthorizedError):
            await client.request("GET", "/rest/api/3/issue/DEMO-1")
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
        (302, ProviderUnavailableError),
        (500, ProviderUnavailableError),
        (400, InvalidRequestError),
    ],
)
async def test_error_bodies_redirects_and_tokens_do_not_escape(status, error):
    lease, _ = lease_for()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={"error": "synthetic-jira-access"},
            headers={"Location": "https://evil.invalid", "Retry-After": "nan"},
        )

    client = JiraClient(lease, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(error) as raised:
            await client.request("GET", "/rest/api/3/issue/DEMO-1")
        assert "synthetic-jira-access" not in str(raised.value)
        assert len(calls) == (2 if status == 401 else 1)
    finally:
        await client.aclose()


async def test_timeout_write_is_not_retried():
    lease, _ = lease_for()
    calls = []

    def handler(request):
        calls.append(request)
        msg = "synthetic-jira-access"
        raise httpx.ReadTimeout(msg, request=request)

    client = JiraClient(lease, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IntegrationNetworkError) as raised:
            await client.request("POST", "/rest/api/3/issue", body={"fields": {}})
        assert len(calls) == 1
        assert "synthetic-jira-access" not in str(raised.value)
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "value", ['DEMO" OR project = SECRET', "https://evil.invalid", "DEMO/../SECRET", "demo", "A\n"]
)
def test_project_keys_cannot_inject_jql(value):
    with pytest.raises(InvalidRequestError):
        search_body(value)


def test_cloud_id_is_operator_uuid(monkeypatch):
    monkeypatch.setenv("LANGFLOW_JIRA_CLOUD_ID", "https://evil.invalid")
    with pytest.raises(InvalidRequestError):
        cloud_id()
    assert issue_key("DEMO-123") == "DEMO-123"
    assert project_key("DEMO") == "DEMO"
    assert numeric_id("31") == "31"


def test_standalone_bundle_discovery_blocks_server_imports():
    import lfx_jira

    class NoServer(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002 - import finder protocol
            if fullname == "langflow" or fullname.startswith("langflow."):
                msg = "Bundle imports the backend"
                raise AssertionError(msg)

    blocker = NoServer()
    sys.meta_path.insert(0, blocker)
    try:
        path = Path(lfx_jira.__file__).parent
        assert validate_extension(path).ok
        loaded = load_extension(path, distribution="lfx-jira")
        assert loaded.ok, loaded.errors
        assert len(loaded.components) == 8
        assert len(load_manifest().capabilities) == 8
        node = JiraOnIssueCreatedTriggerComponent(connection="jira/work", project="DEMO")
        assert node.trigger_config() == {"connection": "jira/work", "project": "DEMO", "delivery_mode": "poll"}
    finally:
        sys.meta_path.remove(blocker)
