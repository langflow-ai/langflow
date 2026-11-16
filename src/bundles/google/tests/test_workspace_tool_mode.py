"""Exercise Workspace actions through the generated agent tools."""

from __future__ import annotations

import base64
import email
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FLOW_ID, RUN_ID, RecordedHttp, json_response, load_fixture
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_google.components.google import (
    GmailSendComponent,
    GoogleCalendarCreateComponent,
    GoogleCalendarListComponent,
    GoogleDriveFetchComponent,
    GoogleDriveListComponent,
)


@pytest.mark.parametrize(
    ("component_class", "required", "argument", "argument_type", "output_count"),
    [
        (GmailSendComponent, {"to", "subject", "body"}, "to", "array", 1),
        (GoogleCalendarCreateComponent, {"summary", "start_time", "end_time"}, "attendees", "array", 1),
        (GoogleCalendarListComponent, set(), "single_events", "boolean", 2),
        (GoogleDriveFetchComponent, {"file_id"}, "supports_all_drives", "boolean", 1),
        (GoogleDriveListComponent, set(), "page_size", "integer", 2),
    ],
)
async def test_workspace_tools_expose_runtime_arguments_without_connections(
    component_class, required, argument, argument_type, output_count
):
    tools = await component_class().to_toolkit()

    assert len(tools) == output_count
    for tool in tools:
        schema = tool.args_schema.model_json_schema()
        assert set(schema.get("required", [])) == required
        assert schema["properties"][argument]["type"] == argument_type
        assert "connection" not in schema["properties"]
        assert "attachments" not in schema["properties"]
        for field in schema["properties"].values():
            if field.get("type") == "array" and "default" in field:
                assert field["default"] == []


def _tool_component(monkeypatch, component_class, responses, **values):
    http = RecordedHttp(responses)
    monkeypatch.setattr(component_class, "_workspace_http", http, raising=False)
    principal = ExecutionPrincipal(kind="actor", user_id="user-1", interactive=True)
    vertex = SimpleNamespace(
        outputs=[],
        graph=SimpleNamespace(
            execution_principal=principal,
            flow_id=FLOW_ID,
            _run_id=RUN_ID,
            authorized_legacy_flow_ids=frozenset({FLOW_ID}),
        ),
    )
    component = component_class(connection="google/work", _vertex=vertex, _tracing_service=None, **values)
    return component, http, principal


async def test_drive_tool_repeated_calls_use_current_arguments_and_configured_connection(monkeypatch, resolver):
    component, http, principal = _tool_component(
        monkeypatch,
        GoogleDriveListComponent,
        [json_response("drive_list_response"), json_response("drive_list_response")],
    )
    tools = await component.to_toolkit()
    listing = next(tool for tool in tools if tool.name == "list_page")

    for query, page_token in (("name contains 'first'", ""), ("name contains 'second'", "page-2")):
        result = await listing.ainvoke({"query": query, "page_token": page_token, "page_size": 3})
        assert result["next_page_token"] == load_fixture("drive_list_response")["nextPageToken"]

    assert len(http.request_sequence) == 2
    requests = [parse_qs(urlparse(request[0]).query) for request in http.request_sequence]
    assert requests[0]["q"] == ["name contains 'first'"]
    assert "pageToken" not in requests[0]
    assert requests[1]["q"] == ["name contains 'second'"]
    assert requests[1]["pageToken"] == ["page-2"]
    assert requests[1]["pageSize"] == ["3"]
    assert len(resolver.requests) == 2
    assert all(request.ref.to_handle() == "google/work" for request in resolver.requests)
    assert all(request.principal == principal for request in resolver.requests)
    assert all(request.flow_id == FLOW_ID for request in resolver.requests)


async def test_gmail_tool_sends_each_invocation_with_the_current_arguments(monkeypatch, resolver):
    component, http, principal = _tool_component(
        monkeypatch,
        GmailSendComponent,
        [json_response("gmail_send_response"), json_response("gmail_send_response")],
    )
    tool = (await component.to_toolkit())[0]

    for subject in ("First report", "Second report"):
        result = await tool.ainvoke({"to": ["recipient@example.com"], "subject": subject, "body": "Report body."})
        assert result == load_fixture("gmail_send_response")

    messages = [
        email.message_from_bytes(base64.urlsafe_b64decode(json.loads(request[2])["raw"]))
        for request in http.request_sequence
    ]
    assert [message["Subject"] for message in messages] == ["First report", "Second report"]
    assert all(message["To"] == "recipient@example.com" for message in messages)
    assert len(resolver.requests) == 2
    assert all(request.ref.to_handle() == "google/work" for request in resolver.requests)
    assert all(request.principal == principal for request in resolver.requests)
