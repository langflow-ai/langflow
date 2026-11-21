"""Signed GitLab deliveries reach the documented Parser and action inputs."""

import json
from functools import partial

import httpx
import pytest
from langflow.api.v2.workflow import _parse_persisted_workflow_request
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher
from langflow.services.triggers.constants import FAMILY_TRIGGER_PUSH
from langflow.services.triggers.service import TriggerService
from langflow.services.triggers.source_clients import source_lease
from lfx.components.processing.parser import ParserComponent
from lfx.graph import Graph
from lfx.processing.process import process_tweaks
from lfx_gitlab.base import GitLabActionComponent
from lfx_gitlab.client import GitLabClient
from lfx_gitlab.components import gitlab as components

from tests.unit.services.triggers.test_gitlab_lifecycle import connection, gitlab, reconcile  # noqa: F401
from tests.unit.services.triggers.test_gitlab_provider import payload, signed

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("kind", ["issue", "merge_request"])
async def test_signed_event_flows_through_documented_parsers_into_update(
    gitlab,  # noqa: ARG001, F811
    trigger_owner,
    owned_flow,
    client,
    fake_background_service,
    monkeypatch,
    kind,
):
    await connection(trigger_owner)
    trigger = await reconcile(owned_flow, trigger_owner, kind=kind)
    async with session_scope() as session:
        row = await session.get(Trigger, trigger.id)
        await TriggerService().enable_and_activate(session, row=row)
        secret = decrypt_api_key(row.signing_secret_encrypted)
        public_id = row.public_id
        lease = await source_lease(session, row, family=FAMILY_TRIGGER_PUSH)

    value = payload(f"gitlab.{kind}")
    value["object_attributes"]["title"] = "Event title"
    request = signed(value, secret=secret)
    response = await client.post(
        f"/api/v1/triggers/ingress/gitlab/{public_id}", content=request.body, headers=request.headers
    )
    assert response.status_code == 202, response.text
    assert await dispatcher.run_once(owner="gitlab-parser-test") == 1
    assert len(fake_background_service.submits) == 1
    parsed = _parse_persisted_workflow_request(fake_background_service.submits[0]["request"])

    trigger_class, update_class = (
        (components.GitLabOnIssueTriggerComponent, components.GitLabUpdateIssueComponent)
        if kind == "issue"
        else (components.GitLabOnMergeRequestTriggerComponent, components.GitLabUpdateMergeRequestComponent)
    )
    event_component = trigger_class(_id=trigger.node_id, connection="gitlab/work", project_id=80)
    frontend_node = event_component.to_frontend_node()
    node = frontend_node.get("data", frontend_node)
    canvas = {
        "nodes": [{"id": trigger.node_id, "data": {"id": trigger.node_id, "node": node["node"]}}],
        "edges": [],
    }
    tweaked = process_tweaks(canvas, parsed.tweaks, stream=False)
    template = tweaked["nodes"][0]["data"]["node"]["template"]
    event_component.set(**{name: field.get("value") for name, field in template.items() if isinstance(field, dict)})
    assert event_component.build_event().data["trigger_id"] == str(trigger.id)
    project = ParserComponent(_id="project", pattern="{payload[delivery][project][id]}").set(
        input_data=event_component.build_event
    )
    number = ParserComponent(_id="number", pattern="{payload[delivery][object_attributes][iid]}").set(
        input_data=event_component.build_event
    )
    title = ParserComponent(_id="title", pattern="{payload[delivery][object_attributes][title]} [handled]").set(
        input_data=event_component.build_event
    )
    update = update_class(_id="update", connection="gitlab/work").set(
        project_id=project.parse_combined_text,
        number=number.parse_combined_text,
        title=title.parse_combined_text,
    )
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": 100, "iid": 4})

    monkeypatch.setattr("lfx_gitlab.base.GitLabClient", partial(GitLabClient, transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(GitLabActionComponent, "resolve_connection", lambda _self, _field: lease)
    graph = Graph(start=event_component, end=update)
    results = [result async for result in graph.async_start()]

    assert results
    assert graph.get_vertex("update").built_object["result"].data == {"id": 100, "iid": 4}
    expected_resource = "issues" if kind == "issue" else "merge_requests"
    assert len(requests) == 1
    assert requests[0].method == "PUT"
    assert requests[0].url.path == f"/api/v4/projects/80/{expected_resource}/4"
    assert json.loads(requests[0].content) == {"title": "Event title [handled]"}
