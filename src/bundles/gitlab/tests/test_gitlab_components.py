"""Real component requests and installed manifest contracts."""

import json
from functools import partial
from pathlib import Path

import httpx
import pytest
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import InvalidRequestError
from lfx_gitlab.client import GitLabClient
from lfx_gitlab.components import gitlab

CASES = [
    (gitlab.GitLabGetProjectComponent, "GET", "/projects/80", {}),
    (gitlab.GitLabGetIssueComponent, "GET", "/projects/80/issues/4", {"number": 4}),
    (gitlab.GitLabCreateIssueComponent, "POST", "/projects/80/issues", {"title": "one", "body_content": "body"}),
    (
        gitlab.GitLabUpdateIssueComponent,
        "PUT",
        "/projects/80/issues/4",
        {"number": 4, "title": "one", "body_content": "body", "state_event": "close"},
    ),
    (gitlab.GitLabGetMergeRequestComponent, "GET", "/projects/80/merge_requests/4", {"number": 4}),
    (
        gitlab.GitLabCreateMergeRequestComponent,
        "POST",
        "/projects/80/merge_requests",
        {"title": "one", "body_content": "body", "source_branch": "feature", "target_branch": "main"},
    ),
    (
        gitlab.GitLabUpdateMergeRequestComponent,
        "PUT",
        "/projects/80/merge_requests/4",
        {"number": 4, "title": "one", "body_content": "body", "state_event": "close"},
    ),
    (gitlab.GitLabCreateIssueCommentComponent, "POST", "/projects/80/issues/4/notes", {"number": 4, "body": "reply"}),
    (
        gitlab.GitLabCreateMergeRequestCommentComponent,
        "POST",
        "/projects/80/merge_requests/4/notes",
        {"number": 4, "body": "reply"},
    ),
]


@pytest.mark.parametrize(("cls", "method", "path", "values"), CASES)
async def test_action_requests_and_per_run_cache(monkeypatch, lease, cls, method, path, values):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": len(requests), "token": "redact-me"})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(cls, "resolve_connection", lambda _self, _field: lease)
    component = cls(connection="gitlab/work", project_id=80, **values)
    result = await component.build_result()
    assert result.data == {"id": 1}
    assert (await component.build_result()).data == result.data
    assert len(requests) == 1
    assert requests[0].method == method
    assert requests[0].url.path == "/api/v4" + path
    assert requests[0].headers["private-token"] == "test-only-gitlab-token"
    if method != "GET":
        assert json.loads(requests[0].content) == {
            "description" if key == "body_content" else key: value for key, value in values.items() if key != "number"
        }
    component._pre_run_setup()
    assert (await component.build_result()).data == {"id": 2}


@pytest.mark.parametrize("cls", [gitlab.GitLabUpdateIssueComponent, gitlab.GitLabUpdateMergeRequestComponent])
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"title": "Rename only"}, {"title": "Rename only"}),
        ({"body_content": "New description"}, {"description": "New description"}),
        ({"state_event": "close"}, {"state_event": "close"}),
    ],
)
async def test_partial_updates_preserve_unspecified_fields(monkeypatch, lease, cls, fields, expected):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": 4})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(cls, "resolve_connection", lambda _self, _field: lease)
    component = cls(connection="gitlab/work", project_id=80, number=4, **fields)
    await component.build_result()
    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert json.loads(requests[0].content) == expected


@pytest.mark.parametrize("cls", [gitlab.GitLabUpdateIssueComponent, gitlab.GitLabUpdateMergeRequestComponent])
async def test_empty_updates_do_not_resolve_credentials_or_send_requests(monkeypatch, cls):
    monkeypatch.setattr(cls, "resolve_connection", lambda *_args: pytest.fail("Empty update resolved credentials"))
    component = cls(connection="gitlab/work", project_id=80, number=4)
    with pytest.raises(InvalidRequestError, match="Provide a new title, description, or state change"):
        await component.build_result()


def test_manifest_stable_classes_and_scope_contract():
    root = Path(__file__).parents[1] / "src/lfx_gitlab"
    manifest = IntegrationCapabilityManifest.model_validate_json(
        (root / "components/gitlab/capabilities.v1.json").read_text()
    )
    assert manifest.provider_id == "gitlab"
    assert len(manifest.capabilities) == 11
    for capability in manifest.capabilities:
        cls = getattr(gitlab, capability.component_ref)
        field = next(field for field in cls.inputs if field.name == "connection")
        assert field.provider == "gitlab"
        assert field.capabilities == [capability.id]
        assert field.required_scopes == ["api"]
        assert all("token" not in item.name and "secret" not in item.name for item in cls.inputs)
    assert json.loads((root / "extension.json").read_text()) == json.loads(
        (root.parent.parent / "extension.json").read_text()
    )


@pytest.mark.parametrize("cls", [gitlab.GitLabOnIssueTriggerComponent, gitlab.GitLabOnMergeRequestTriggerComponent])
def test_trigger_definition_contains_no_credentials(cls):
    component = cls(connection="gitlab/work", project_id=80, actions=["open"])
    definition = component.trigger_definition()
    assert definition.provider == "gitlab"
    assert definition.config["project_id"] == 80
    assert definition.config["include_self_events"] is False
    assert component.build_event().data == {}
