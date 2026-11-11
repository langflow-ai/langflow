"""Dedicated Slack actions accept agent arguments through the standard toolkit."""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.custom import Component  # noqa: TC002 - initialize the component package before loading Slack
from lfx_slack import (
    SlackAddReactionComponent,
    SlackCanvasComponent,
    SlackListChannelMembersComponent,
    SlackPostAsAppComponent,
    SlackReadThreadComponent,
    SlackSearchComponent,
    SlackSendAsUserComponent,
)


def _tool_component(component_class: type[Component], **kwargs) -> Component:
    attached = build_component(component_class, **kwargs)
    attached._vertex.outputs = []
    return component_class(connection="slack/workspace", _vertex=attached._vertex, **kwargs)


@pytest.mark.parametrize(
    ("component_class", "arguments", "output_methods"),
    [
        (
            SlackSearchComponent,
            {"query", "count", "sort", "sort_dir", "cursor"},
            {"build_matches", "build_pagination"},
        ),
        (
            SlackReadThreadComponent,
            {"channel", "ts", "limit", "cursor", "oldest", "latest"},
            {"build_messages", "build_pagination"},
        ),
        (SlackSendAsUserComponent, {"channel", "text", "thread_ts", "blocks", "unfurl_links"}, {"build_message"}),
        (SlackCanvasComponent, {"title", "markdown", "channel_id"}, {"build_canvas"}),
        (
            SlackPostAsAppComponent,
            {"channel", "text", "thread_ts", "reply_broadcast", "blocks", "attachments", "unfurl_links"},
            {"build_message"},
        ),
        (SlackAddReactionComponent, {"channel", "timestamp", "emoji_name"}, {"slack_add_reaction_component"}),
        (
            SlackListChannelMembersComponent,
            {"channel", "channel_is_private", "resolve_names", "limit", "cursor"},
            {"build_members", "build_pagination"},
        ),
    ],
)
async def test_action_tool_schemas_keep_connections_configured(component_class, arguments, output_methods) -> None:
    tools = await _tool_component(component_class).to_toolkit()

    assert {tool.name for tool in tools} == output_methods
    for tool in tools:
        assert set(tool.args_schema.model_fields) == arguments
        assert "connection" not in tool.args_schema.model_fields


async def test_search_tools_use_each_calls_arguments_and_preserve_the_execution_principal(
    transport: SlackTransport, resolver: FakeResolver
) -> None:
    for _ in range(3):
        transport.enqueue(load_fixture("search_messages"))
    component = _tool_component(SlackSearchComponent)
    tools = {tool.name: tool for tool in await component.to_toolkit()}

    matches = await tools["build_matches"].ainvoke({"query": "deploy", "count": 5})
    await tools["build_matches"].ainvoke({"query": "rollback", "cursor": "page-2"})
    pagination = await tools["build_pagination"].ainvoke({"query": "rollback", "cursor": "page-2"})

    assert len(matches) == 2
    assert [call.params["query"] for call in transport.calls] == ["deploy", "rollback", "rollback"]
    assert transport.calls[0].params["count"] == 5
    assert transport.calls[1].params["cursor"] == "page-2"
    assert pagination["next_cursor"] == "dXNlcjpVMDYxTkZUVDI="
    assert all(request.ref.name == "workspace" for request in resolver.requests)
    assert all(request.principal.user_id == "user-1" for request in resolver.requests)
    assert all(request.flow_id == "flow-1" for request in resolver.requests)
    assert component.query == ""


@pytest.mark.parametrize(
    ("component_class", "identity", "token"),
    [
        (SlackSendAsUserComponent, "user_delegated", "xoxp-user-token"),
        (SlackPostAsAppComponent, "bot", "xoxb-bot-token"),
    ],
)
async def test_message_tools_accept_json_blocks_and_execute_each_write(
    transport: SlackTransport, monkeypatch: pytest.MonkeyPatch, component_class, identity, token
) -> None:
    resolver = FakeResolver(identity=identity, tokens=[token])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    for _ in range(2):
        transport.enqueue(load_fixture("chat_postmessage"))
    component = _tool_component(component_class)
    [tool] = await component.to_toolkit()

    await tool.ainvoke({"channel": "C0SLACKDEMO", "text": "first"})
    arguments = {
        "channel": "C0SLACKDEMO",
        "text": "second",
        "unfurl_links": False,
        "blocks": [{"type": "section", "text": {"type": "plain_text", "text": "Second"}}],
    }
    if component_class is SlackPostAsAppComponent:
        arguments["attachments"] = [{"color": "#36a64f", "text": "green"}]
    await tool.ainvoke(arguments)

    assert [call.params["text"] for call in transport.calls] == ["first", "second"]
    assert "blocks" not in transport.calls[0].params
    assert transport.calls[1].params["blocks"] == arguments["blocks"]
    if component_class is SlackPostAsAppComponent:
        assert transport.calls[1].params["attachments"] == arguments["attachments"]
    assert transport.calls[1].params["unfurl_links"] is False
    assert all(call.authorization == f"Bearer {token}" for call in transport.calls)
    assert all(request.principal.user_id == "user-1" for request in resolver.requests)


async def test_member_tool_arguments_control_the_required_scopes(
    transport: SlackTransport, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolver = FakeResolver(identity="bot", tokens=["xoxb-bot-token"])
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    transport.enqueue(load_fixture("conversations_members"))
    for _ in range(2):
        transport.enqueue(load_fixture("users_info"))
    tools = {tool.name: tool for tool in await _tool_component(SlackListChannelMembersComponent).to_toolkit()}

    await tools["build_members"].ainvoke({"channel": "C0SLACKDEMO", "channel_is_private": True, "resolve_names": True})

    assert resolver.requests[0].required_scopes == frozenset({"channels:read", "groups:read", "users:read"})
    assert [call.method for call in transport.calls] == ["conversations.members", "users.info", "users.info"]
