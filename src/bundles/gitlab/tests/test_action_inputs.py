"""Action inputs accept parsed events and identify invalid fields."""

import json
from functools import partial

import httpx
import pytest
from lfx.components.processing.parser import ParserComponent
from lfx.custom.utils import create_component_template
from lfx.graph import Graph
from lfx.integrations.errors import InvalidRequestError
from lfx.schema.data import Data
from lfx_gitlab.base import GitLabActionComponent
from lfx_gitlab.client import GitLabClient
from lfx_gitlab.components import gitlab

ACTION_CLASSES = [getattr(gitlab, name) for name in gitlab.__all__ if not name.startswith("GitLabOn")]


@pytest.mark.parametrize("component_class", ACTION_CLASSES)
def test_action_palette_exposes_message_handles(component_class):
    template, _ = create_component_template(
        component_extractor=component_class(), module_name=component_class.__module__
    )
    for name in ("project_id", "number", "title", "source_branch", "target_branch"):
        if name in template["template"]:
            assert "Message" in (template["template"][name]["input_types"] or [])
    if "number" in template["template"]:
        expected = "Issue Number" if component_class.resource == "issue" else "Merge Request Number"
        assert template["template"]["number"]["display_name"] == expected


@pytest.mark.parametrize(
    "component_class", [gitlab.GitLabUpdateIssueComponent, gitlab.GitLabUpdateMergeRequestComponent]
)
async def test_update_targets_the_item_from_parser_outputs(monkeypatch, lease, component_class):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": 40, "iid": 4})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(component_class, "resolve_connection", lambda _self, _field: lease)
    event = Data(data={"project_id": 80, "number": 4, "title": "Updated from an event"})
    fields = {
        name: ParserComponent(input_data=event, pattern="{" + name + "}").parse_combined_text()
        for name in ("project_id", "number", "title")
    }
    component = component_class(connection="gitlab/work")
    component.set_attributes(fields)
    assert (await component.build_result()).data == {"id": 40, "iid": 4}
    expected_resource = "issues" if component_class.resource == "issue" else "merge_requests"
    assert requests[0].url.path == f"/api/v4/projects/80/{expected_resource}/4"
    assert json.loads(requests[0].content) == {"title": "Updated from an event"}


async def test_issue_event_flows_through_parsers_into_update(monkeypatch, lease):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": 40, "iid": 4})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(GitLabActionComponent, "resolve_connection", lambda _self, _field: lease)
    trigger = gitlab.GitLabOnIssueTriggerComponent(
        _id="issue_event",
        connection="gitlab/work",
        project_id=80,
        event_payload=json.dumps({"project": {"id": 80}, "object_attributes": {"iid": 4, "title": "Event title"}}),
    )
    project = ParserComponent(_id="project", pattern="{project[id]}").set(input_data=trigger.build_event)
    number = ParserComponent(_id="number", pattern="{object_attributes[iid]}").set(input_data=trigger.build_event)
    title = ParserComponent(_id="title", pattern="{object_attributes[title]}").set(input_data=trigger.build_event)
    update = gitlab.GitLabUpdateIssueComponent(_id="update", connection="gitlab/work").set(
        project_id=project.parse_combined_text,
        number=number.parse_combined_text,
        title=title.parse_combined_text,
    )
    graph = Graph(start=trigger, end=update)
    results = [result async for result in graph.async_start()]

    assert results
    assert graph.get_vertex("update").built_object["result"].data == {"id": 40, "iid": 4}
    assert requests[0].url.path == "/api/v4/projects/80/issues/4"
    assert json.loads(requests[0].content) == {"title": "Event title"}


@pytest.mark.parametrize("value", [-1, 0, 2**63])
async def test_invalid_project_id_names_field_and_range(monkeypatch, value):
    monkeypatch.setattr(
        gitlab.GitLabGetProjectComponent, "resolve_connection", lambda *_args: pytest.fail("Resolved credential")
    )
    component = gitlab.GitLabGetProjectComponent(connection="gitlab/work", project_id=value)
    with pytest.raises(InvalidRequestError, match=r"Project ID.*1.*9223372036854775807"):
        await component.build_result()


@pytest.mark.parametrize(
    ("component_class", "label"),
    [(gitlab.GitLabGetIssueComponent, "Issue Number"), (gitlab.GitLabGetMergeRequestComponent, "Merge Request Number")],
)
async def test_invalid_item_number_names_the_resource(component_class, label):
    component = component_class(connection="gitlab/work", project_id=80, number=-1)
    with pytest.raises(InvalidRequestError, match=label):
        await component.build_result()


async def test_blank_comment_names_the_required_text():
    component = gitlab.GitLabCreateIssueCommentComponent(connection="gitlab/work", project_id=80, number=4, body="   ")
    with pytest.raises(InvalidRequestError, match="Comment must contain non-whitespace text"):
        await component.build_result()
