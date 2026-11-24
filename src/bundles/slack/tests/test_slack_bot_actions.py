"""Recorded-fixture contract tests for the three bot-identity actions."""

from __future__ import annotations

import pytest
from conftest import FakeResolver, SlackTransport, build_component, load_fixture
from lfx.schema.data import Data
from lfx_slack import (
    SlackAddReactionComponent,
    SlackListChannelMembersComponent,
    SlackPostAsAppComponent,
)


@pytest.fixture
def bot_resolver(monkeypatch: pytest.MonkeyPatch) -> FakeResolver:
    fake = FakeResolver(identity="bot", tokens=["xoxb-bot-token"], owner_kind="instance")  # pragma: allowlist secret
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: fake)
    return fake


@pytest.mark.usefixtures("bot_resolver")
async def test_post_as_app_sends_every_declared_parameter(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("chat_postmessage"))
    component = build_component(
        SlackPostAsAppComponent,
        channel="C0SLACKDEMO",
        text="release is out",
        thread_ts="1700000000.000100",
        reply_broadcast=True,
        blocks=[Data(data={"type": "divider"})],
        attachments=[Data(data={"color": "#36a64f", "text": "green"})],
        unfurl_links=True,
    )

    message = await component.build_message()

    assert transport.last.method == "chat.postMessage"
    params = transport.last.params
    assert params["reply_broadcast"] is True
    assert params["blocks"] == [{"type": "divider"}]
    assert params["attachments"] == [{"color": "#36a64f", "text": "green"}]
    assert transport.last.authorization == "Bearer xoxb-bot-token"
    assert message.data["channel"] == "C0SLACKDEMO"


@pytest.mark.usefixtures("bot_resolver")
async def test_add_reaction_strips_colons_and_sends_the_web_api_name(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("reactions_add"))
    component = build_component(
        SlackAddReactionComponent,
        channel="C0SLACKDEMO",
        timestamp="1700000200.000400",
        emoji_name=":thumbsup:",
    )

    result = await component.build_result()

    assert transport.last.method == "reactions.add"
    params = transport.last.params
    assert params["name"] == "thumbsup"
    assert params["channel"] == "C0SLACKDEMO"
    assert params["timestamp"] == "1700000200.000400"
    assert result.data["ok"] is True
    assert result.data["name"] == "thumbsup"


@pytest.mark.usefixtures("bot_resolver", "transport")
async def test_add_reaction_requires_every_field() -> None:
    component = build_component(SlackAddReactionComponent, channel="C0", timestamp="1.0", emoji_name="::")

    with pytest.raises(ValueError, match="Emoji name is required"):
        await component.build_result()


@pytest.mark.usefixtures("bot_resolver")
async def test_list_channel_members_returns_ids_and_a_cursor(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("conversations_members"))
    component = build_component(
        SlackListChannelMembersComponent,
        channel="C0SLACKDEMO",
        limit=50,
        cursor="members-page-1",
    )

    members = await component.build_members()
    pagination = await component.build_pagination()

    assert transport.last.method == "conversations.members"
    params = transport.last.params
    assert params["channel"] == "C0SLACKDEMO"
    assert params["limit"] == 50
    assert params["cursor"] == "members-page-1"
    assert [m.data for m in members] == [{"id": "U0SLACKUSER"}, {"id": "U0SLACKMATE"}]
    assert pagination.data["next_cursor"] == "bWVtYmVycy1wYWdlLTI="
    assert len(transport.calls) == 1


@pytest.mark.usefixtures("bot_resolver")
async def test_resolve_names_calls_users_info_per_member(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("conversations_members"))
    transport.enqueue(load_fixture("users_info"))
    transport.enqueue(load_fixture("users_info"))
    component = build_component(SlackListChannelMembersComponent, channel="C0SLACKDEMO", resolve_names=True)

    members = await component.build_members()

    assert [call.method for call in transport.calls] == [
        "conversations.members",
        "users.info",
        "users.info",
    ]
    assert transport.calls[1].params["user"] == "U0SLACKUSER"
    assert transport.calls[2].params["user"] == "U0SLACKMATE"
    assert members[0].data["display_name"] == "avery"
    assert members[0].data["real_name"] == "Avery Rivers"
    assert members[0].data["is_bot"] is False


@pytest.mark.usefixtures("bot_resolver")
async def test_last_page_reports_no_cursor(transport: SlackTransport) -> None:
    transport.enqueue(load_fixture("conversations_members_last_page"))
    component = build_component(SlackListChannelMembersComponent, channel="C0SLACKDEMO")

    pagination = await component.build_pagination()

    assert pagination.data["next_cursor"] is None
