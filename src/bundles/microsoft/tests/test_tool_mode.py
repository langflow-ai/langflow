"""Agent tools retain configured connections and send runtime action arguments."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from lfx_microsoft import (
    OutlookCalendarCreateComponent,
    OutlookCalendarListComponent,
    OutlookSearchComponent,
    OutlookSendComponent,
    SharePointFetchComponent,
    SharePointListComponent,
    TeamsChannelPostComponent,
    TeamsChatPostComponent,
)
from lfx_microsoft.base import MicrosoftGraphComponent
from microsoft_testkit import TransportRecorder, credential, json_response, stub_graph
from pydantic import TypeAdapter


@pytest.mark.parametrize(
    ("component_class", "parameters", "output_count"),
    [
        (
            OutlookCalendarCreateComponent,
            {
                "subject",
                "start_time",
                "end_time",
                "time_zone",
                "body",
                "location",
                "attendees",
                "is_online_meeting",
                "calendar_id",
                "transaction_id",
                "recurrence",
            },
            1,
        ),
        (
            OutlookCalendarListComponent,
            {"start_time", "end_time", "calendar_id", "top", "select", "time_zone"},
            2,
        ),
        (OutlookSearchComponent, {"search", "filter", "folder_id", "top", "select", "include_body"}, 2),
        (OutlookSendComponent, {"to", "cc", "bcc", "subject", "body", "body_is_html", "save_to_sent_items"}, 1),
        (SharePointFetchComponent, {"item_id", "path", "drive_id", "site_id", "range", "max_bytes"}, 1),
        (SharePointListComponent, {"drive_id", "site_id", "item_id", "path", "top", "select", "order_by"}, 2),
        (TeamsChannelPostComponent, {"team_id", "channel_id", "content", "content_type", "mentions", "attachments"}, 1),
        (TeamsChatPostComponent, {"chat_id", "content", "content_type", "mentions", "attachments"}, 1),
    ],
)
async def test_action_tool_schemas_keep_connections_configured(component_class, parameters, output_count):
    component = component_class(connection="microsoft/work")

    tools = await component.to_toolkit()

    assert len(tools) == output_count
    for tool in tools:
        assert set(tool.args_schema.model_fields) == parameters
        assert "connection" not in tool.args_schema.model_json_schema()["properties"]
        for field in tool.args_schema.model_fields.values():
            if not field.is_required():
                assert TypeAdapter(field.annotation).validate_python(field.default) == field.default


async def test_mail_tool_sends_changed_arguments_and_keeps_uploaded_files(
    monkeypatch, resolver_factory, user_storage_dir
):
    resolver = resolver_factory(credential(scopes={"Mail.Send"}))
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    monkeypatch.setattr(MicrosoftGraphComponent, "graph_transport", recorder.transport)
    attachment = user_storage_dir / "notes.txt"
    attachment.write_bytes(b"hello")
    component = OutlookSendComponent(
        _vertex=SimpleNamespace(graph=stub_graph(), outputs=[]),
        _user_id=user_storage_dir.name,
        connection="microsoft/work",
        attachments=[str(attachment)],
    )
    [tool] = await component.to_toolkit()

    for subject in ("First update", "Second update"):
        result = await tool.ainvoke(
            {"to": ["ada@contoso.com"], "subject": subject, "body": subject, "save_to_sent_items": False}
        )
        assert result["subject"] == subject

    assert len(recorder.requests) == 2
    for request, subject in zip(recorder.requests, ("First update", "Second update"), strict=True):
        assert request.url.path == "/v1.0/me/sendMail"
        assert request.headers["authorization"] == "Bearer graph-token-1"
        payload = json.loads(request.content)
        assert payload["message"]["subject"] == subject
        assert payload["message"]["body"] == {"contentType": "text", "content": subject}
        assert payload["saveToSentItems"] is False
        assert payload["message"]["attachments"][0]["contentBytes"] == "aGVsbG8="
    assert {request.ref.name for request in resolver.requests} == {"work"}
    assert {request.principal.user_id for request in resolver.requests} == {"user-1"}


async def test_search_tools_keep_results_and_pagination_as_separate_actions(monkeypatch, resolver_factory):
    resolver_factory(credential(scopes={"Mail.Read"}))
    next_link = "https://graph.microsoft.com/v1.0/me/messages?%24skip=1"
    recorder = TransportRecorder(
        lambda request: json_response(
            {
                "value": [{"id": request.url.params["$search"]}],
                "@odata.nextLink": next_link,
            }
        )
    )
    monkeypatch.setattr(MicrosoftGraphComponent, "graph_transport", recorder.transport)
    component = OutlookSearchComponent(
        _vertex=SimpleNamespace(graph=stub_graph(), outputs=[]), connection="microsoft/work"
    )
    results_tool, pagination_tool = await component.to_toolkit()

    for query in ("budget", "forecast"):
        result = await results_tool.ainvoke({"search": query, "top": 1, "select": ["id", "subject"]})
        assert result == [{"data": {"id": f'"{query}"'}, "text_key": "text", "default_value": ""}]
    assert await pagination_tool.ainvoke({"search": "forecast", "top": 1}) == next_link

    assert len(recorder.requests) == 3
    assert [request.url.params["$search"] for request in recorder.requests] == ['"budget"', '"forecast"', '"forecast"']
    assert recorder.first.url.params["$select"] == "id,subject"


async def test_chat_tool_sends_structured_runtime_payloads(monkeypatch, resolver_factory):
    resolver_factory(credential(scopes={"ChatMessage.Send"}))
    recorder = TransportRecorder(lambda _request: json_response({"id": "message-1"}, status_code=201))
    monkeypatch.setattr(MicrosoftGraphComponent, "graph_transport", recorder.transport)
    mentions = [{"id": 0, "mentionText": "Ada"}]
    attachments = [{"id": "card-1", "contentType": "application/vnd.microsoft.card.adaptive"}]
    component = TeamsChatPostComponent(
        _vertex=SimpleNamespace(graph=stub_graph(), outputs=[]),
        connection="microsoft/work",
    )
    [tool] = await component.to_toolkit()

    result = await tool.ainvoke(
        {
            "chat_id": "chat-1",
            "content": "Hello Ada",
            "content_type": "html",
            "mentions": mentions,
            "attachments": attachments,
        }
    )

    assert result == {"id": "message-1"}
    assert recorder.last.url.path == "/v1.0/chats/chat-1/messages"
    assert json.loads(recorder.last.content) == {
        "body": {"contentType": "html", "content": "Hello Ada"},
        "mentions": mentions,
        "attachments": attachments,
    }
