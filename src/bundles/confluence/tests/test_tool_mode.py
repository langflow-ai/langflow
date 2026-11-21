"""Confluence tool calls retain approved spaces and page version checks."""

import json
from types import SimpleNamespace

import httpx
import pytest
from conftest import Resolver, credential, page
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_confluence.base import ConfluenceActionComponent
from lfx_confluence.client import ConfluenceClient
from lfx_confluence.components.confluence_integrations import (
    ConfluenceCreatePageComponent,
    ConfluenceReadPageComponent,
    ConfluenceSearchPagesComponent,
    ConfluenceUpdatePageComponent,
)


def tool_component(component_class):
    graph = SimpleNamespace(
        execution_principal=ExecutionPrincipal(kind="actor", user_id="owner", interactive=True),
        flow_id="flow-1",
        run_id="run-1",
        session_id="session-1",
    )
    return component_class(connection="confluence/work", _vertex=SimpleNamespace(graph=graph, outputs=[]))


@pytest.mark.parametrize(
    ("component_class", "arguments"),
    [
        (ConfluenceSearchPagesComponent, {"space_id", "title", "cursor"}),
        (ConfluenceReadPageComponent, {"space_id", "page_id"}),
        (ConfluenceCreatePageComponent, {"space_id", "title", "body_storage", "parent_id"}),
        (ConfluenceUpdatePageComponent, {"space_id", "page_id", "expected_version", "title", "body_storage"}),
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
        ConfluenceActionComponent,
        "client",
        lambda component: ConfluenceClient(
            component.resolve_connection("connection"), transport=httpx.MockTransport(handler)
        ),
    )
    return resolver


async def test_search_tool_uses_new_arguments_and_returns_continuation(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        title = request.url.params.get("title", "Example")
        return httpx.Response(
            200, json={"results": [page(title=title)], "_links": {"next": "/wiki/api/v2/pages?cursor=next-page"}}
        )

    resolver = install_client(monkeypatch, handler)
    [tool] = await tool_component(ConfluenceSearchPagesComponent).to_toolkit()

    first = await tool.ainvoke({"space_id": "10", "title": "First"})
    second = await tool.ainvoke({"space_id": "10", "title": "Second", "cursor": first["next_cursor"]})

    assert first["pages"][0]["title"] == "First"
    assert second["pages"][0]["title"] == "Second"
    assert len(requests) == 2
    assert requests[1].url.params["cursor"] == "next-page"
    assert all(request.principal.user_id == "owner" for request in resolver.calls)
    assert all(request.ref.name == "work" for request in resolver.calls)
    assert all(request.flow_id == "flow-1" for request in resolver.calls)


async def test_tool_arguments_cannot_select_an_unapproved_space(monkeypatch):
    resolver = install_client(monkeypatch, lambda _request: pytest.fail("Unexpected request"))
    [tool] = await tool_component(ConfluenceSearchPagesComponent).to_toolkit()

    refused = await tool.ainvoke({"space_id": "99"})

    assert "not approved by the deployment operator" in refused
    assert resolver.calls == []


async def test_update_tool_preserves_the_expected_version_check(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=page(version=4))
        return httpx.Response(200, json=page(version=5))

    resolver = install_client(monkeypatch, handler)
    [tool] = await tool_component(ConfluenceUpdatePageComponent).to_toolkit()
    arguments = {"space_id": "10", "page_id": "1", "title": "Changed", "body_storage": "<p>Changed</p>"}

    result = await tool.ainvoke({**arguments, "expected_version": 4})
    refused = await tool.ainvoke({**arguments, "expected_version": 3})

    assert result["version"] == 5
    assert "The page changed" in refused
    assert [request.method for request in requests] == ["GET", "PUT", "GET"]
    assert json.loads(requests[1].content)["version"] == {"number": 5}
    assert json.loads(requests[1].content)["body"]["value"] == "<p>Changed</p>"
    assert all(request.principal.user_id == "owner" for request in resolver.calls)
