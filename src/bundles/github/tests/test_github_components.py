"""Component requests, identity declarations, manifests, and graph safety."""

import json
from functools import partial
from pathlib import Path

import httpx
import pytest
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx_github.client import GitHubClient
from lfx_github.components import github

CASES = [
    (github.GitHubGetRepositoryComponent, "GET", "/repos/org/repo", {}),
    (github.GitHubGetIssueComponent, "GET", "/repos/org/repo/issues/4", {"number": 4}),
    (github.GitHubCreateIssueComponent, "POST", "/repos/org/repo/issues", {"title": "one", "body": "body"}),
    (
        github.GitHubUpdateIssueComponent,
        "PATCH",
        "/repos/org/repo/issues/4",
        {"number": 4, "title": "one", "body": "body", "state": "closed"},
    ),
    (github.GitHubGetPullRequestComponent, "GET", "/repos/org/repo/pulls/4", {"number": 4}),
    (
        github.GitHubCreatePullRequestComponent,
        "POST",
        "/repos/org/repo/pulls",
        {"title": "one", "body": "body", "head": "feature", "base": "main"},
    ),
    (
        github.GitHubUpdatePullRequestComponent,
        "PATCH",
        "/repos/org/repo/pulls/4",
        {"number": 4, "title": "one", "body": "body", "state": "closed"},
    ),
    (github.GitHubCreateCommentComponent, "POST", "/repos/org/repo/issues/4/comments", {"number": 4, "body": "body"}),
]


@pytest.mark.parametrize(("cls", "method", "path", "values"), CASES)
async def test_all_actions_send_bounded_inputs_and_rebuild(monkeypatch, lease, cls, method, path, values):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": len(requests)})

    monkeypatch.setattr("lfx_github.base.GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(cls, "resolve_connection", lambda _self, _field: lease)
    component = cls(connection="github/work", repository="org/repo", **values)
    first = await component.build_result()
    assert (await component.build_result()).data == first.data
    assert len(requests) == 2
    assert requests[-1].method == method
    assert requests[-1].url.path == path
    if method in {"POST", "PATCH"}:
        body = json.loads(requests[-1].content)
        assert body == {key: value for key, value in values.items() if key != "number"}
    component._pre_run_setup()
    assert (await component.build_result()).data != first.data
    assert len(requests) == 4


def test_manifest_matches_stable_components_and_connection_scopes():
    root = Path(__file__).parents[1] / "src/lfx_github"
    manifest = IntegrationCapabilityManifest.model_validate_json(
        (root / "components/github/capabilities.v1.json").read_text()
    )
    assert manifest.provider_id == "github"
    assert len(manifest.capabilities) == 10
    for capability in manifest.capabilities:
        cls = getattr(github, capability.component_ref)
        field = next(field for field in cls.inputs if field.name == "connection")
        assert field.provider == "github"
        assert field.auth_profile_id == "github-installation"
        assert set(field.required_scopes) == set(capability.required_scopes)
        assert capability.id in field.capabilities
        assert all("token" not in field.name and "secret" not in field.name for field in cls.inputs)
    assert json.loads((root / "extension.json").read_text()) == json.loads(
        (root.parent.parent / "extension.json").read_text()
    )


@pytest.mark.parametrize("cls", [github.GitHubOnIssueTriggerComponent, github.GitHubOnPullRequestTriggerComponent])
def test_trigger_declaration_stores_reference_and_filters(cls):
    node = cls(connection="github/work", repository="org/repo", actions=["opened"])
    definition = node.trigger_definition()
    assert definition.provider == "github"
    assert definition.needs_connection
    assert definition.config == {
        "connection": "github/work",
        "repository": "org/repo",
        "actions": ["opened"],
        "delivery_mode": "push",
        "include_bot_events": False,
    }
    assert node.build_event().data == {}


@pytest.mark.parametrize(
    ("cls", "resource"),
    [(github.GitHubUpdateIssueComponent, "issues"), (github.GitHubUpdatePullRequestComponent, "pulls")],
)
@pytest.mark.parametrize("changes", [{"title": "Changed title"}, {"body": "Changed body"}, {"state": "open"}])
async def test_partial_updates_preserve_omitted_fields(monkeypatch, lease, cls, resource, changes):
    requests = []
    stored = {"id": 4, "title": "Existing title", "body": "Existing body", "state": "closed"}

    def handle(request):
        requests.append(request)
        if request.method == "PATCH":
            stored.update(json.loads(request.content))
        return httpx.Response(200, json=stored)

    monkeypatch.setattr("lfx_github.base.GitHubClient", partial(GitHubClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(cls, "resolve_connection", lambda _self, _field: lease)
    component = cls(connection="github/work", repository="org/repo", number=4, **changes)
    result = await component.build_result()

    assert requests[-1].method == "PATCH"
    assert requests[-1].url.path == f"/repos/org/repo/{resource}/4"
    assert json.loads(requests[-1].content) == changes
    assert result.data == {"id": 4, "title": "Existing title", "body": "Existing body", "state": "closed", **changes}


@pytest.mark.parametrize("cls", [github.GitHubUpdateIssueComponent, github.GitHubUpdatePullRequestComponent])
async def test_empty_update_fails_before_resolving_credentials(monkeypatch, cls):
    from lfx.integrations.errors import InvalidRequestError

    monkeypatch.setattr(
        cls, "resolve_connection", lambda _self, _field: pytest.fail("An empty update resolved credentials")
    )
    component = cls(connection="github/work", repository="org/repo", number=4)
    with pytest.raises(InvalidRequestError, match="Provide a new title, body, or state"):
        await component.build_result()
