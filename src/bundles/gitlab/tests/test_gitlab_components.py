"""Real component requests and installed manifest contracts."""

import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from conftest import Resolver
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.integrations.errors import InvalidRequestError
from lfx.services.authorization.base import ExecutionPrincipal
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
async def test_action_tools_use_runtime_arguments_and_configured_connection(monkeypatch, cls, method, path, values):
    requests = []
    resolutions = []

    class RecordingResolver(Resolver):
        async def resolve(self, request):
            resolutions.append(request)
            return await super().resolve(request)

    resolver = RecordingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    monkeypatch.delenv("LANGFLOW_GITLAB_ORIGIN", raising=False)

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": len(requests)})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    principal = ExecutionPrincipal(kind="actor", user_id="owner", interactive=True)
    vertex = SimpleNamespace(outputs=[], graph=SimpleNamespace(execution_principal=principal, flow_id="flow-1"))
    component = cls(connection="gitlab/work", _vertex=vertex, _tracing_service=None)
    tool = (await component.to_toolkit())[0]
    schema = tool.args_schema.model_json_schema()
    assert schema["properties"]["project_id"]["type"] == "integer"
    assert "project_id" in schema["required"]
    assert "connection" not in schema["properties"]
    assert tool.name != "build_result"

    assert await tool.ainvoke({"project_id": 80, **values}) == {"id": 1}
    assert await tool.ainvoke({"project_id": 90, **values}) == {"id": 2}

    assert [request.method for request in requests] == [method, method]
    assert [request.url.path for request in requests] == ["/api/v4" + path, "/api/v4" + path.replace("80", "90")]
    if method != "GET":
        expected_body = {
            "description" if key == "body_content" else key: value for key, value in values.items() if key != "number"
        }
        assert all(json.loads(request.content) == expected_body for request in requests)
    assert len(resolutions) == 2
    assert all(request.ref.to_handle() == "gitlab/work" for request in resolutions)
    assert all(request.principal == principal for request in resolutions)


@pytest.mark.parametrize("cls", [gitlab.GitLabOnIssueTriggerComponent, gitlab.GitLabOnMergeRequestTriggerComponent])
def test_trigger_inputs_do_not_enable_tool_mode(cls):
    assert not any(getattr(field, "tool_mode", False) for field in cls.inputs)


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
