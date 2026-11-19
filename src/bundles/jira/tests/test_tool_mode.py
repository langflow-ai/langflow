"""Jira actions retain their connection and policies when called as tools."""

import json
from types import SimpleNamespace

import httpx
import pytest
from conftest import Resolver, credential, issue
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_jira.base import JiraActionComponent
from lfx_jira.client import JiraClient
from lfx_jira.components.jira import (
    JiraCreateIssueComponent,
    JiraReadIssueComponent,
    JiraSearchIssuesComponent,
    JiraTransitionIssueComponent,
    JiraUpdateIssueComponent,
)


def tool_component(component_class):
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        flow_id="flow-1",
        run_id="run-1",
        session_id="session-1",
    )
    return component_class(connection="jira/work", _vertex=SimpleNamespace(graph=graph, outputs=[]))


@pytest.mark.parametrize(
    ("component_class", "arguments"),
    [
        (JiraSearchIssuesComponent, {"project", "status_id", "page"}),
        (JiraReadIssueComponent, {"issue"}),
        (JiraCreateIssueComponent, {"project", "issue_type_id", "summary", "description_text"}),
        (JiraUpdateIssueComponent, {"issue", "summary", "description_text"}),
        (JiraTransitionIssueComponent, {"issue", "transition_id"}),
    ],
)
async def test_action_schemas_expose_runtime_arguments_without_the_connection(component_class, arguments):
    [tool] = await tool_component(component_class).to_toolkit()

    assert set(tool.args_schema.model_fields) == arguments
    assert "connection" not in tool.args_schema.model_fields


def install_client(monkeypatch, handler):
    resolver = Resolver([credential()])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    monkeypatch.setattr(
        JiraActionComponent,
        "client",
        lambda component: JiraClient(
            component.resolve_connection("connection"), transport=httpx.MockTransport(handler)
        ),
    )
    return resolver


async def test_search_tool_uses_new_arguments_and_returns_continuation(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"issues": [issue()], "nextPageToken": "next-page", "isLast": False})

    resolver = install_client(monkeypatch, handler)
    [tool] = await tool_component(JiraSearchIssuesComponent).to_toolkit()

    first = await tool.ainvoke({"project": "DEMO"})
    await tool.ainvoke({"project": "DEMO", "status_id": "1", "page": first["next_page_token"]})

    assert first["issues"][0]["key"] == "DEMO-1"
    assert len(requests) == 2
    assert json.loads(requests[0].content)["jql"] == 'project = "DEMO" ORDER BY key ASC'
    assert json.loads(requests[1].content)["nextPageToken"] == "next-page"
    assert json.loads(requests[1].content)["jql"] == 'project = "DEMO" AND status = "1" ORDER BY key ASC'
    assert all(request.principal.user_id == "owner" for request in resolver.calls)
    assert all(request.ref.name == "work" for request in resolver.calls)
    assert all(request.flow_id == "flow-1" for request in resolver.calls)


async def test_create_tool_uses_agent_fields_and_the_configured_credential(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"id": "1", "key": "DEMO-1"})

    resolver = install_client(monkeypatch, handler)
    [tool] = await tool_component(JiraCreateIssueComponent).to_toolkit()

    result = await tool.ainvoke(
        {"project": "DEMO", "issue_type_id": "10001", "summary": "Created by the agent", "description_text": "Details"}
    )

    assert result == {"id": "1", "key": "DEMO-1"}
    [request] = requests
    assert request.method == "POST"
    fields = json.loads(request.content)["fields"]
    assert fields["summary"] == "Created by the agent"
    assert fields["description"]["content"][0]["content"][0]["text"] == "Details"
    assert request.headers["authorization"] == "Bearer synthetic-jira-access"
    assert resolver.calls[0].principal.user_id == "owner"
