"""Recorded-fixture contract tests for the two Teams post actions."""

from __future__ import annotations

import json

import pytest
from lfx.integrations.errors import ScopeMissingError
from lfx.schema.data import Data
from lfx_microsoft import TeamsChannelPostComponent, TeamsChatPostComponent
from microsoft_testkit import TransportRecorder, build_component, credential, graph_error, graph_fixture, json_response


async def test_chat_post_targets_the_chat_messages_collection(resolver_factory) -> None:
    resolver_factory(credential(scopes={"ChatMessage.Send"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("chat_message_created"), status_code=201))
    component = build_component(
        TeamsChatPostComponent,
        recorder,
        connection="microsoft/work",
        chat_id="19:chat-id@thread.v2",
        content="Deployment finished.",
    )

    result = await component.post_message()

    request = recorder.last
    assert request.method == "POST"
    assert request.url.path == "/v1.0/chats/19:chat-id@thread.v2/messages"
    assert json.loads(request.content) == {"body": {"contentType": "text", "content": "Deployment finished."}}
    assert result.data["id"] == "1756640000000"


async def test_chat_post_carries_html_mentions_and_attachments(resolver_factory) -> None:
    resolver_factory(credential(scopes={"ChatMessage.Send"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("chat_message_created"), status_code=201))
    component = build_component(
        TeamsChatPostComponent,
        recorder,
        connection="microsoft/work",
        chat_id="19:chat-id@thread.v2",
        content="<at id='0'>Ada</at> ship it",
        content_type="html",
        mentions=[Data(data={"id": 0, "mentionText": "Ada"})],
        attachments=[{"id": "card-1", "contentType": "application/vnd.microsoft.card.adaptive"}],
    )

    await component.post_message()

    payload = json.loads(recorder.last.content)
    assert payload["body"]["contentType"] == "html"
    assert payload["mentions"] == [{"id": 0, "mentionText": "Ada"}]
    assert payload["attachments"] == [{"id": "card-1", "contentType": "application/vnd.microsoft.card.adaptive"}]


async def test_chat_post_requires_the_chat_message_send_scope(resolver_factory) -> None:
    resolver_factory(credential(scopes={"ChannelMessage.Send"}))
    recorder = TransportRecorder(lambda _request: json_response({}, status_code=201))
    component = build_component(
        TeamsChatPostComponent,
        recorder,
        connection="microsoft/work",
        chat_id="19:chat-id@thread.v2",
        content="hello",
    )

    with pytest.raises(ScopeMissingError):
        await component.post_message()
    assert recorder.requests == []


async def test_channel_post_targets_the_channel_messages_collection(resolver_factory) -> None:
    resolver_factory(credential(scopes={"ChannelMessage.Send"}))
    recorder = TransportRecorder(
        lambda _request: json_response(graph_fixture("channel_message_created"), status_code=201)
    )
    component = build_component(
        TeamsChannelPostComponent,
        recorder,
        connection="microsoft/work",
        team_id="team-1",
        channel_id="19:channel@thread.tacv2",
        content="Release notes are up.",
    )

    result = await component.post_message()

    request = recorder.last
    assert request.url.path == "/v1.0/teams/team-1/channels/19:channel@thread.tacv2/messages"
    assert json.loads(request.content)["body"]["content"] == "Release notes are up."
    assert result.data["webUrl"].startswith("https://teams.microsoft.com/")


async def test_channel_post_surfaces_a_graph_denial_as_scope_missing(resolver_factory) -> None:
    resolver_factory(credential(scopes=set(), scopes_verified=False))
    recorder = TransportRecorder(lambda _request: graph_error("Authorization_RequestDenied", 403))
    component = build_component(
        TeamsChannelPostComponent,
        recorder,
        connection="microsoft/work",
        team_id="team-1",
        channel_id="19:channel@thread.tacv2",
        content="hello",
    )

    with pytest.raises(ScopeMissingError):
        await component.post_message()
    # Unverified scopes skip the pre-flight, so the denial comes from Graph.
    assert len(recorder.requests) == 1
